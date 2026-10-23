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
            before = {x['metadata']['name']: x['spec']['template']['spec']['containers'][0]['image'] for x in live if x['kind']=='Deployment' and x['metadata']['name'] in ['backend','frontend']}
            after = {x['metadata']['name']: x['spec']['template']['spec']['containers'][0]['image'] for x in target if x['kind']=='Deployment' and x['metadata']['name'] in ['backend','frontend']}
            self.assertEqual(before, after)
            self.assertFalse(any(x['kind']=='Deployment' and x['metadata']['name']=='postgres-deployment' for x in target))
            cluster = next(x for x in target if x['kind']=='Cluster')
            self.assertIn('@sha256:', cluster['spec']['imageName'])
            self.assertNotIn('backup', cluster['spec'])
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
