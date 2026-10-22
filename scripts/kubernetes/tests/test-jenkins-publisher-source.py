#!/usr/bin/env python3
"""Verify pinned publisher input, unsafe-entry rejection and private diagnostics."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare-jenkins-publisher-source.py'
MODULE = runpy.run_path(str(SCRIPT))
SECRET = 'FAKE-PUBLISHER-SOURCE-SECRET-ONLY-02ca'


class PublisherSourceTests(unittest.TestCase):
    def invoke(self, wrong_remote=False, unsafe_mode=False, corrupt_blob=False, existing=False, git_failure=False, observer=False):
        content = ('# fixture ' + SECRET + '\n').encode()
        oid = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()

        def command(arguments, **kwargs):
            command = arguments[3:]
            if command[:2] == ['remote', 'get-url']:
                result = b'https://example.invalid/other.git' if wrong_remote else ('git@github.com:' + MODULE['SOURCE_REPOSITORY'] + '.git').encode()
            elif command[0] == 'rev-parse':
                result = MODULE['SOURCE_COMMIT'].encode()
            elif command[0] == 'ls-tree':
                mode = '120000' if unsafe_mode else '100644'
                result = b''.join(f'{mode} blob {oid}\tci/{name}\0'.encode() for name in
                                  ['registry.py', 'phase1.py', 'candidate.py', 'promote.py', 'publish.sh',
                                   'promote-stage.sh', 'publisher-action.sh', 'stage_acceptance.py', 'validate_gitops.py', 'validate.sh'])
            else:
                self.assertEqual(command[:2], ['cat-file', 'blob'])
                result = b'changed' if corrupt_blob else content
            return subprocess.CompletedProcess(arguments, int(git_failure), result, SECRET.encode())

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'bundle.json'
            if existing:
                output.write_text(SECRET)
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch('subprocess.run', side_effect=command), \
                    patch.object(sys, 'argv', [str(SCRIPT), '--output', str(output)] + (['--observer'] if observer else [])), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                status = 0
                try:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
                except SystemExit as result:
                    status = result.code
            failed = wrong_remote or unsafe_mode or corrupt_blob or existing or git_failure
            self.assertEqual(status, 1 if failed else 0)
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
            if existing:
                self.assertEqual(output.read_text(), SECRET)
            elif not failed:
                bundle = json.loads(output.read_text())
                self.assertIs(bundle['immutable'], True)
                self.assertEqual(bundle['data']['stage_acceptance.py' if observer else 'registry.py'].encode(), content)
                if observer:
                    self.assertEqual(set(bundle['data']), {'stage_acceptance.py'})
                    self.assertEqual(bundle['metadata']['namespace'], 'jenkins-acceptance')
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            else:
                self.assertFalse(output.exists())

    def test_preserves_pinned_source_bytes_without_executing_or_printing(self):
        self.invoke()

    def test_observer_bundle_excludes_all_writer_helpers(self):
        self.invoke(observer=True)

    def test_wrong_repository_is_rejected(self):
        self.invoke(wrong_remote=True)

    def test_symlink_is_rejected(self):
        self.invoke(unsafe_mode=True)

    def test_changed_blob_is_rejected(self):
        self.invoke(corrupt_blob=True)

    def test_existing_reviewed_output_is_preserved(self):
        self.invoke(existing=True)

    def test_git_failure_does_not_leak_diagnostics(self):
        self.invoke(git_failure=True)


if __name__ == '__main__':
    unittest.main()
