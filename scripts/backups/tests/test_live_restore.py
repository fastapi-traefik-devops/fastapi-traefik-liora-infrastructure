"""Offline checks: source protection, unchanged images and live-target refusal."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import os
import yaml
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive import location, wal_prefix
spec = importlib.util.spec_from_file_location('live_restore', Path(__file__).resolve().parents[1] / 'prepare-live-restore.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
spec_i = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install-recovery-overlay.py')
i = importlib.util.module_from_spec(spec_i); spec_i.loader.exec_module(i)


class RecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects = {env: r.render(env) for env in ['dev', 'stage', 'prod']}

    def test_all_environment_bundles_preserve_images_and_protect_source(self):
        for env, original in self.objects.items():
            with self.subTest(environment=env):
                before = copy.deepcopy(original)
                files, target, server = r.build(original, env, '20261025T020007', '2026-10-25T03:00:00Z', None, None, 'incident-1')
                source, writer, cluster = files['database.yaml']
                self.assertNotIn('retentionPolicy', source['spec'])
                self.assertEqual(source['spec']['configuration']['destinationPath'], 's3://liora-backup/' + env + '/')
                self.assertNotEqual(target, source['spec']['configuration']['destinationPath'])
                self.assertEqual(writer['spec']['configuration']['destinationPath'], target)
                self.assertEqual(location(cluster, writer)['server'], server)
                self.assertNotIn('initdb', cluster['spec']['bootstrap'])
                old = r.select(original, 'Cluster', 'liora-db')
                for key in ['instances', 'affinity', 'storage', 'resources', 'imageName']:
                    self.assertEqual(cluster['spec'][key], old['spec'][key])
                apps = [o for o in files['application.yaml'] if o['kind'] == 'Deployment']
                held = [o for o in files['maintenance.yaml'] if o['kind'] == 'Deployment']
                self.assertTrue(apps)
                self.assertTrue(all(o['spec']['replicas'] == 0 for o in held))
                for app in apps:
                    previous = r.select(original, 'Deployment', app['metadata']['name'])
                    self.assertEqual(app['spec']['template'], previous['spec']['template'])
                self.assertTrue(files['prestart.yaml'])
                self.assertEqual(original, before)
                self.assertNotIn('Secret', [o.get('kind') for docs in files.values() for o in docs])

    def test_gitops_install_keeps_other_settings_and_last_patch_wins(self):
        for env in self.objects:
            with self.subTest(environment=env), tempfile.TemporaryDirectory(dir=r.ROOT / '.local-work') as tmp:
                root = Path(tmp); overlay = root / 'kubernetes/apps/liora/overlays' / env
                overlay.mkdir(parents=True)
                # Apply the original environment's existing destination/server patches again
                # before the generated late patches. This reproduces the override hazard.
                original = yaml.safe_load((r.ROOT / 'kubernetes/apps/liora/overlays' / env / 'kustomization.yaml').read_text())
                value = {'apiVersion': 'kustomize.config.k8s.io/v1beta1', 'kind': 'Kustomization',
                         'resources': [os.path.relpath(r.ROOT / 'kubernetes/apps/liora/overlays' / env, overlay)],
                         'commonAnnotations': {'fixture-concurrent-change': 'preserve'},
                         'patches': original.get('patches', [])}
                (overlay / 'kustomization.yaml').write_text(yaml.safe_dump(value))
                files, _, _ = r.build(self.objects[env], env, '20261025T020007', '2026-10-25T03:00:00Z', None, None, 'fixture')
                bundle = root / 'bundle'; bundle.mkdir()
                for name, docs in files.items():
                    path = bundle / name; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(yaml.safe_dump(docs) if name.endswith('-patch.yaml') else yaml.safe_dump_all(docs))
                application_path = bundle / 'application.yaml'
                application_before = application_path.read_bytes()
                changed = list(yaml.safe_load_all(application_before))
                next(o for o in changed if o['kind'] == 'Deployment')['spec']['template']['spec']['containers'][0]['image'] = 'fixture@sha256:changed'
                application_path.write_text(yaml.safe_dump_all(changed))
                with patch.object(i, 'ROOT', root):
                    with self.assertRaises(ValueError): i.install(env, bundle)
                self.assertFalse((overlay / 'recovery').exists())
                application_path.write_bytes(application_before)
                with patch.object(i, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                    i.install(env, bundle)
                    with self.assertRaises(ValueError): i.install(env, bundle)
                result = subprocess.check_output(['kubectl', 'kustomize', str(overlay)])
                objects = list(yaml.safe_load_all(result))
                for wanted in files['database.yaml']:
                    actual = r.select(objects, wanted['kind'], wanted['metadata']['name'])
                    self.assertEqual(actual['spec'], wanted['spec'])
                self.assertEqual(i.images(objects), i.images(files['application.yaml']))
                updated = yaml.safe_load((overlay / 'kustomization.yaml').read_text())
                self.assertEqual(updated['commonAnnotations'], value['commonAnnotations'])
                self.assertEqual(updated['patches'][:len(value['patches'])], value['patches'])

    def test_live_cluster_or_pvc_refused_before_secret_provisioning(self):
        for cluster, claims in [(b'{"metadata":{"name":"liora-db"}}', []), (b'', [{}])]:
            with patch.object(r, 'command', side_effect=[cluster, json.dumps({'items': claims}).encode(), b'{"items":[]}', b'{"items":[]}']) as cmd:
                with self.assertRaises(r.RecoveryError):
                    r.check_empty_target(Path('fixture'), 'dev')
                self.assertTrue(all('get' in call.args[0] for call in cmd.call_args_list))

    def test_running_writers_refused(self):
        for deployments, jobs in [([{'spec': {'replicas': 1}}], []), ([], [{'status': {'active': 1}}])]:
            outputs = [b'', b'{"items":[]}', json.dumps({'items': deployments}).encode(), json.dumps({'items': jobs}).encode()]
            with patch.object(r, 'command', side_effect=outputs):
                with self.assertRaises(r.RecoveryError): r.check_empty_target(Path('fixture'), 'dev')

    def test_catalog_output_excludes_sensitive_backup_metadata(self):
        class Body(io.BytesIO): pass
        class S3:
            def list_objects_v2(self, **kw): return {'Contents': [{'Key': 'dev/liora-dev/base/20261025T020149/backup.info'}]}
            def get_object(self, **kw): return {'Body': Body(b'status=DONE\nconninfo=password=FIXTURE_SECRET_CANARY\nend_time=2026-10-25 02:02:00+00:00\n')}
        result = r.backup_catalog(S3(), 'liora-backup', 'dev/', 'liora-dev')
        self.assertNotIn('FIXTURE_SECRET_CANARY', json.dumps(result))
        self.assertEqual(result[0]['backup_id'], '20261025T020149')

    def test_error_output_does_not_echo_external_exception_secret(self):
        stream = io.StringIO()
        with patch.object(sys, 'argv', ['prepare', 'catalog', '--environment', 'dev']), patch.object(r, 'render', side_effect=RuntimeError('FIXTURE_SECRET_CANARY')), contextlib.redirect_stderr(stream):
            self.assertEqual(r.main(), 1)
        self.assertNotIn('FIXTURE_SECRET_CANARY', stream.getvalue())

    def test_archive_tracks_recovery_identity(self):
        files, _, _ = r.build(self.objects['dev'], 'dev', '20261025T020149', '2026-10-25T03:00:00Z', None, None, 'incident-1')
        _, writer, cluster = files['database.yaml']
        path = wal_prefix(location(cluster, writer), '000000010000000000000021')
        self.assertTrue(path.startswith('dev/recovery-incident-1/liora-dev-r-incident-1/wals/'))

    def test_invalid_target_inputs_refused(self):
        for backup, target, identity in [('backup-resource-name', '2026-10-25T03:00:00Z', 'ok'), ('20261025T020149', '2026-10-25T03:00:00', 'ok'), ('20261025T020149', '2026-10-25T03:00:00Z', '../bad')]:
            with self.assertRaises(ValueError): r.build(self.objects['dev'], 'dev', backup, target, None, None, identity)


if __name__ == '__main__': unittest.main()
