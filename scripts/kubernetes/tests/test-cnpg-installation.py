"""Check independent database transitions and unchanged application images."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[3]


def render(path):
    return list(yaml.safe_load_all(subprocess.check_output(['kubectl', 'kustomize', str(path)])))


class InstallationTests(unittest.TestCase):
    def test_transition_is_opt_in_and_retains_image_pair(self):
        # Build component variants inside the checkout; no repository copy.
        for env in ['dev', 'stage', 'prod']:
            overlay = ROOT / 'kubernetes/apps/liora/overlays' / env
            current = yaml.safe_load((overlay / 'kustomization.yaml').read_text())
            live = render(overlay)
            with tempfile.TemporaryDirectory(dir=ROOT / 'kubernetes/apps/liora/overlays') as tmp:
                candidate = copy.deepcopy(current)
                candidate['components'] = ['../../components/cloudnative-pg']
                # Existing same-directory files are referenced explicitly.
                candidate['resources'] = [str(overlay / x) if not x.startswith('..') else x for x in candidate['resources']]
                Path(tmp, 'kustomization.yaml').write_text(yaml.safe_dump(candidate))
                # kubectl restricts loading external files; use a symlink-free
                # local kustomization with shared base/component resources only.
                candidate['resources'] = ['../../base']
                Path(tmp, 'kustomization.yaml').write_text(yaml.safe_dump(candidate))
                target = render(tmp)
            backend = next(x for x in target if x['kind']=='Deployment' and x['metadata']['name']=='backend')
            self.assertIn('liora.aprt.info/database', backend['spec']['template']['metadata']['annotations'])
            before = {x['metadata']['name']: x['spec']['template']['spec']['containers'][0]['image'] for x in live if x['kind']=='Deployment' and x['metadata']['name'] in ['backend','frontend']}
            after = {x['metadata']['name']: x['spec']['template']['spec']['containers'][0]['image'] for x in target if x['kind']=='Deployment' and x['metadata']['name'] in ['backend','frontend']}
            self.assertEqual(before, after)
            self.assertFalse(any(x['kind']=='Deployment' and x['metadata']['name']=='postgres-deployment' for x in target))
            cluster = next(x for x in target if x['kind']=='Cluster')
            self.assertIn('@sha256:', cluster['spec']['imageName'])
            self.assertNotIn('backup', cluster['spec'])
            self.assertFalse(cluster['spec']['enablePDB'])
            self.assertEqual(cluster['spec']['affinity']['podAntiAffinityType'], 'required')
            self.assertEqual(cluster['spec']['instances'], 2 if env == 'prod' else 1)
            self.assertNotIn('synchronous', cluster['spec']['postgresql'])
            service = next(x for x in target if x['kind']=='Service' and x['metadata']['name']=='db')
            self.assertEqual(service['spec']['selector'], {'cnpg.io/cluster':'liora-db','role':'primary'})
            owner = next(x for x in target if x['kind']=='ConfigMap' and x['metadata']['name']=='backend-config')
            self.assertEqual(owner['data']['POSTGRES_USER'], 'app_owner')

    def test_split_render_supports_current_database_platforms(self):
        import os
        import runpy
        for env in ['dev', 'stage', 'prod']:
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, 'all.yaml').write_text(yaml.safe_dump_all(render(ROOT/'kubernetes/apps/liora/overlays'/env)))
                with patch.dict(os.environ, render_dir=tmp, namespace='app-'+env), patch('sys.stdout', io.StringIO()):
                    runpy.run_path(str(ROOT/'scripts/kubernetes/split-application-render.py'))
                database=list(yaml.safe_load_all(Path(tmp, 'database.yaml').read_text()))
                self.assertEqual(len(database), 2)
                self.assertTrue(any(x['kind']=='Service' and x['metadata']['name']=='db' for x in database))

    def test_operator_bootstrap_image_is_digest_pinned(self):
        operator=next(x for x in render(ROOT/'kubernetes/platform/cloudnative-pg') if x['kind']=='Deployment')
        container=operator['spec']['template']['spec']['containers'][0]
        injected=next(x['value'] for x in container['env'] if x['name']=='OPERATOR_IMAGE_NAME')
        self.assertIn('@sha256:',container['image'])
        self.assertEqual(injected,container['image'])

    def test_password_table_uses_cnpg_administrative_credentials(self):
        import base64
        spec=importlib.util.spec_from_file_location('passwords', ROOT/'recovery/show_passwords.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        encoded=base64.b64encode(b'fixture-password-table-canary').decode()
        seen=[]
        def read(config, namespace, kind, name):
            seen.append(name)
            if name=='backend-config':return {'POSTGRES_USER':'app_owner','FIRST_SUPERUSER':'fake@example.invalid'}
            if name=='backend-secrets':return {'FIRST_SUPERUSER_PASSWORD':encoded}
            if name=='cnpg-superuser':return {'username':base64.b64encode(b'postgres').decode(),'password':encoded}
            if name=='argocd-initial-admin-secret':return {'password':encoded}
            if name=='monitoring-grafana-admin':return {'admin-user':base64.b64encode(b'admin').decode(),'admin-password':encoded}
            if name=='jenkins-foundation-login':return {'jenkins-admin-password':encoded}
            raise AssertionError('Unexpected credential resource')
        with patch.object(module,'read_data',side_effect=read):rows=module.collect({'nonprod':'fake','prod':'fake'})
        self.assertNotIn('db-config',seen)
        self.assertEqual([row[2] for _, group in rows for row in group if row[0]=='Adminer'],['postgres']*3)

    def test_bootstrap_does_not_leak_or_overwrite_secrets(self):
        spec=importlib.util.spec_from_file_location('bootstrap', ROOT/'scripts/kubernetes/bootstrap-cnpg-secrets.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        import base64
        canary='fixture-secret-must-not-be-printed-347'
        encoded=base64.b64encode(canary.encode()).decode()
        secrets={x:{'data':{'POSTGRES_PASSWORD':encoded}} for x in ['db-secrets','backend-secrets']}
        created=[]
        def run(cmd, **kw):
            if 'get' in cmd:
                value=secrets.get(cmd[cmd.index('secret')+1]);return subprocess.CompletedProcess(cmd,0,json.dumps(value).encode() if value else b'')
            obj=json.loads(kw['input']);created.append(obj);return subprocess.CompletedProcess(cmd,0)
        out=io.StringIO()
        with patch.object(module.subprocess,'run',side_effect=run),patch('sys.stdout',out):module.provision('/fixture','dev')
        self.assertNotIn(canary,out.getvalue());self.assertNotIn(encoded,out.getvalue())
        self.assertEqual(len(created),2)
        secrets['cnpg-app']={'type':'kubernetes.io/basic-auth','data':{'password':'different'}}
        with patch.object(module.subprocess,'run',side_effect=run):
            with self.assertRaises(AssertionError) as error:module.provision('/fixture','dev')
        self.assertNotIn(canary,str(error.exception));self.assertEqual(len(created),2)


if __name__=='__main__':unittest.main()
