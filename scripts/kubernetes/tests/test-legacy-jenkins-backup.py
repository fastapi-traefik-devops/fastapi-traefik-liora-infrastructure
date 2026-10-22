#!/usr/bin/env python3
"""Check preservation-copy privacy, archive validation and honest consistency labels."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'backup-legacy-jenkins.py'
SENTINEL = 'FIXTURE-PRIVATE-MATERIAL-ONLY-7f6aa6'


def fixture(names):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in names:
            data = SENTINEL.encode()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return stream.getvalue()


class BackupTests(unittest.TestCase):
    def invoke(self, fail=False, missing_key=False, changed=False):
        source = SCRIPT.read_text()
        home = ['config.xml', 'secrets/master.key', 'secrets/hudson.util.Secret']
        if missing_key:
            home.remove('secrets/master.key')
        runtime = ['run/secrets/jenkins-admin-password', 'run/secrets/github-ci-app-key',
                   'run/secrets/github-gitops-app-key', 'bootstrap/jenkins.yaml', 'bootstrap/jobs.groovy',
                   'opt/phase1-bootstrap/Jenkinsfile', 'opt/phase1-bootstrap/Jenkinsfile.publish']
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[2] / '.local-work') as directory:
            root = Path(directory)
            script = root / 'scripts/kubernetes/backup-legacy-jenkins.py'
            script.parent.mkdir(parents=True)
            script.write_text(source)
            def command(arguments, stdout, **kwargs):
                stdout.write(fixture(home if '/var/jenkins_home' in arguments else runtime))
                return subprocess.CompletedProcess(arguments, 2 if fail else (1 if changed else 0), stderr=SENTINEL.encode())
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch('subprocess.run', side_effect=command), redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    runpy.run_path(str(script), run_name='__main__')
                except SystemExit as result:
                    status = result.code
            self.assertNotIn(SENTINEL, stdout.getvalue() + stderr.getvalue())
            manifests = list(root.glob('.local-work/private/phase9/*/manifest.json'))
            if fail or missing_key:
                self.assertEqual(status, 1)
                self.assertFalse(manifests)
            else:
                self.assertEqual(status, 0)
                manifest = json.loads(manifests[0].read_text())
                self.assertFalse(manifest['consistent'])
                self.assertFalse(manifest['restore_tested'])
                self.assertEqual(len(manifest['archives']), 2)
                for file in manifests[0].parent.iterdir():
                    self.assertEqual(file.stat().st_mode & 0o777, 0o600)
                self.assertEqual(manifests[0].parent.stat().st_mode & 0o777, 0o700)

    def test_private_copy_does_not_claim_consistency_or_print_values(self):
        self.invoke()

    def test_online_changes_remain_explicitly_inconsistent(self):
        self.invoke(changed=True)

    def test_missing_master_key_cannot_pass_validation(self):
        self.invoke(missing_key=True)

    def test_tar_failure_does_not_echo_private_diagnostics(self):
        self.invoke(fail=True)


if __name__ == '__main__':
    unittest.main()
