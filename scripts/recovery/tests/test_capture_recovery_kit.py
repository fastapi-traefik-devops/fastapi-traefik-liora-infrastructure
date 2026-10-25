"""Synthetic coverage for the private-kit staging boundary."""

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'capture-recovery-kit.py'
SPEC = importlib.util.spec_from_file_location('capture_kit', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CaptureKitTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / 'repo'
        (self.repo / 'recovery').mkdir(parents=True)
        for name in MODULE.RECOVERY_INPUTS:
            (self.repo / 'recovery' / name).write_text('fixture-' + name)
        for name in MODULE.PLATFORM_RECORDS:
            path = self.repo / '.local-work/private/platform' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture-' + name)
        for name in MODULE.MODULES:
            path = self.repo / name / 'terraform.tfstate'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture-' + name)
        self.backup = Path(self.temporary.name) / 'jenkins'
        self.backup.mkdir()
        (self.backup / 'home.tar.gz').write_text('synthetic-home')
        home = self.backup / 'home.tar.gz'
        (self.backup / 'manifest.json').write_text(json.dumps({
            'mode': 'stopped-preservation', 'consistent': True,
            'archives': [{'file': 'home.tar.gz', 'bytes': home.stat().st_size,
                          'sha256': hashlib.sha256(home.read_bytes()).hexdigest()}]}))
        (self.backup / 'deployment-before.json').write_text('synthetic-deployment')
        (self.backup / 'configmap-controller.json').write_text('synthetic-configmap')
        self.target = self.repo / 'recovery/kit-fixture'

    def test_capture_and_verify_required_files(self):
        MODULE.capture(self.repo, self.backup, self.target)
        MODULE.verify(self.target)
        self.assertEqual((self.target / 'jenkins-backup/home.tar.gz').read_text(), 'synthetic-home')
        self.assertEqual((self.target / 'edge/tailscale/terraform/terraform.tfstate').read_text(),
                         'fixture-edge/tailscale/terraform')
        self.assertEqual((self.target / '.local-work/private/platform/nonprod-monitoring.json').read_text(),
                         'fixture-nonprod-monitoring.json')
        with self.assertRaises(ValueError):
            MODULE.capture(self.repo, self.backup, self.target)
        (self.target / 'jenkins-backup/home.tar.gz').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            MODULE.verify(self.target)

    def test_missing_state_and_symlink_stop_without_partial_capture(self):
        (self.repo / MODULE.MODULES[0] / 'terraform.tfstate').unlink()
        with self.assertRaises(FileNotFoundError):
            MODULE.capture(self.repo, self.backup, self.target)
        self.assertFalse(self.target.exists())
        (self.repo / MODULE.MODULES[0] / 'terraform.tfstate').write_text('state')
        (self.backup / 'link').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            MODULE.capture(self.repo, self.backup, self.target)
        self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
