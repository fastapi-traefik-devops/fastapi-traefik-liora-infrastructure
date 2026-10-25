"""The reconnect helper changes only a selected overlay patch reference."""

import importlib.util
from pathlib import Path
import tempfile
import unittest

import yaml


SOURCE = Path(__file__).resolve().parents[1] / 'prepare-db-reconnect.py'
SPEC = importlib.util.spec_from_file_location('prepare_db_reconnect', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReconnectTest(unittest.TestCase):
    def test_new_patch_and_refuse_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            overlay = repo / 'kubernetes/apps/liora/overlays/dev'
            overlay.mkdir(parents=True)
            source = overlay / 'kustomization.yaml'
            original = 'images:\n- name: backend\n  digest: sha256:' + 'a' * 64 + '\npatches:\n- path: existing.yaml\n'
            source.write_text(original)
            MODULE.prepare(repo, 'dev', '20261025T120000Z')
            self.assertIn('digest: sha256:' + 'a' * 64, source.read_text())
            self.assertEqual(yaml.safe_load(source.read_text())['patches'][-1]['path'], 'db-reconnect-patch.yaml')
            patch = yaml.safe_load((overlay / 'db-reconnect-patch.yaml').read_text())
            self.assertEqual(patch['spec']['template']['metadata']['annotations']['liora.aprt.info/db-reconnect'],
                             '20261025T120000Z')
            with self.assertRaisesRegex(ValueError, 'already selected'):
                MODULE.prepare(repo, 'dev', '20261025T130000Z')


if __name__ == '__main__':
    unittest.main()
