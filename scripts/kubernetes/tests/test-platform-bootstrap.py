#!/usr/bin/env python3
"""Exercise secret preservation and diagnostic redaction without a live cluster."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'bootstrap-platform-secrets.py'
ROOT = SCRIPT.parents[2]


class BootstrapTests(unittest.TestCase):
    def invoke(self, component, existing=False, failure=False):
        sentinel = 'FIXTURE-SECRET-ONLY-DO-NOT-PRINT-' + 'x' * 32
        calls = []
        with tempfile.TemporaryDirectory(dir=ROOT / '.local-work') as directory:
            root = Path(directory)
            private = root / '.local-work/private/platform'
            private.mkdir(parents=True)
            credential = private / ('nonprod-' + component + '.json')
            credential.write_text(json.dumps({'username': 'fixture-admin', 'password': sentinel}))
            credential.chmod(0o600)
            recovery = root / 'recovery'
            recovery.mkdir()
            (recovery / '.env').write_text('GHCR_REGISTRY=ghcr.io\nGHCR_USERNAME=fixture-user\nGHCR_TOKEN=' + sentinel + '\n')

            def command(arguments, input=None, **kwargs):
                calls.append((arguments, input))
                if 'create' in arguments and failure:
                    return subprocess.CompletedProcess(arguments, 1, sentinel, sentinel)
                output = 'secret/existing' if existing and 'get' in arguments else ''
                return subprocess.CompletedProcess(arguments, 0, output, '')

            output = io.StringIO()
            status = None
            with patch('subprocess.run', side_effect=command), patch('sys.argv', [str(SCRIPT), '--cluster', 'nonprod', '--component', component]), redirect_stdout(output), redirect_stderr(output):
                try:
                    exec(compile(SCRIPT.read_text(), str(SCRIPT), 'exec'),
                         {'__name__': '__main__', '__file__': str(root / 'scripts/kubernetes/bootstrap-platform-secrets.py')})
                except SystemExit as error:
                    status = error.code
            self.assertNotIn(sentinel, output.getvalue(), 'Fixture credential leaked to output')
            self.assertEqual(credential.stat().st_mode & 0o777, 0o600)
            return status, calls

    def test_success_creates_login_without_logging_credentials(self):
        for component in ['monitoring', 'jenkins']:
            with self.subTest(component=component):
                status, calls = self.invoke(component)
                self.assertEqual(status, 0)
                self.assertEqual(sum('create' in arguments for arguments, _ in calls), 1)

    def test_existing_login_is_not_overwritten(self):
        status, calls = self.invoke('monitoring', existing=True)
        self.assertEqual(status, 0)
        self.assertFalse(any('create' in arguments for arguments, _ in calls))

    def test_kubernetes_failure_does_not_echo_secret_diagnostics(self):
        for component in ['monitoring', 'jenkins']:
            with self.subTest(component=component):
                status, _ = self.invoke(component, failure=True)
                self.assertEqual(status, 1)


if __name__ == '__main__':
    unittest.main()
