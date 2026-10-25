"""Synthetic inventory tests for the existing encrypted recovery ZIP."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[3] / 'recovery/archive_inventory.py'
SPEC = importlib.util.spec_from_file_location('archive_inventory', SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ArchiveInventoryTest(unittest.TestCase):
    def test_staged_kit_is_included_and_tracked_source_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            recovery = repo / 'recovery'
            recovery.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            (recovery / 'README.md').write_text('tracked')
            subprocess.run(['git', '-C', str(repo), 'add', 'recovery/README.md'], check=True)
            (recovery / '.env').write_text('synthetic-secret')
            (recovery / 'kit-test/edge/tailscale/terraform').mkdir(parents=True)
            (recovery / 'kit-test/edge/tailscale/terraform/terraform.tfstate').write_text('synthetic-state')
            (recovery / 'kit-test/jenkins-backup').mkdir(parents=True)
            (recovery / 'kit-test/jenkins-backup/home.tar.gz').write_text('synthetic-home')
            files, _ = MODULE.select(repo, recovery)
            names = {relative for _, relative in files}
            self.assertIn('recovery/.env', names)
            self.assertIn('recovery/kit-test/edge/tailscale/terraform/terraform.tfstate', names)
            self.assertIn('recovery/kit-test/jenkins-backup/home.tar.gz', names)
            self.assertNotIn('recovery/README.md', names)
            (recovery / 'unsafe').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(RuntimeError, 'Symbolic links'):
                MODULE.select(repo, recovery)


if __name__ == '__main__':
    unittest.main()
