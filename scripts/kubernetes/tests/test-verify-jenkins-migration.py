#!/usr/bin/env python3
"""Check runtime-verifier login/preservation failures never expose fixture secrets."""

from contextlib import redirect_stderr, redirect_stdout
import base64
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / 'verify-jenkins-migration.py'
SECRET = 'FAKE-VERIFIER-SECRET-ONLY-d04d'


class VerificationTests(unittest.TestCase):
    def invoke(self, invalid_response=False, changed_admin=False, connected_agents=False, offline_agent=False):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[2] / '.local-work') as directory:
            root = Path(directory)
            admin = ('<user><id>admin</id><passwordHash>' + SECRET + '</passwordHash></user>').encode()
            (root / 'current-admin.xml').write_bytes(admin)
            keys = {name: SECRET.encode() for name in ['secrets/master.key', 'secrets/hudson.util.Secret', 'secrets/hudson.model.User.DIRNAMES']}
            expected = {name: hashlib.sha256(data).hexdigest() for name, data in keys.items()}
            expected.update({'users/admin_fixture/config.xml': 'fake', 'users/fixture1/config.xml': 'fake',
                             'users/fixture2/config.xml': 'fake', 'jobs/ci/config.xml': 'fake', 'jobs/ci/builds/1/build.xml': 'fake'})
            (root / 'expected-files.json').write_text(json.dumps(expected))
            report = dict(quiet=True, executors=0, nodes=0, queue=0, users=['admin', 'fixture1', 'fixture2'],
                          persisted_users=['admin', 'fixture1', 'fixture2'], locked_plugins_match=True,
                          additional_plugins=[], item_count=1, job_count=1, jobs_disabled=True, resume_disabled=True,
                          multibranch_disabled=True, builds=1, running_builds=0, plugin_count=84,
                          failed_plugins=0, credentials=[
                              {'scope': 'app-ci', 'id': 'github-ci-app', 'private_key_present': True},
                              {'scope': 'trusted', 'id': 'gitops-app', 'private_key_present': True},
                              {'scope': 'trusted', 'id': 'ghcr-write', 'password_present': True}])
            if connected_agents:
                report['nodes'] = 2
                report['agent_details'] = [dict(name=name, label=name, executors=1, offline=offline_agent)
                                          for name in ('host-ci', 'registry-publisher')]

            def command(arguments, **kwargs):
                if 'secret' in arguments:
                    data = json.dumps({'data': {'jenkins-admin-password': base64.b64encode(SECRET.encode()).decode()}}).encode()
                elif 'sh' in arguments:
                    data = b'blocked\n'
                else:
                    name = arguments[-1].removeprefix('/var/jenkins_home/')
                    data = admin.replace(SECRET.encode(), b'CHANGED') if changed_admin and name.startswith('users/') else admin if name.startswith('users/') else keys[name]
                return subprocess.CompletedProcess(arguments, 0, data, b'')

            def endpoint(request, **kwargs):
                path = request.full_url.split(':8085')[-1]
                if path == '/whoAmI/api/json':
                    value = {'name': 'admin', 'authenticated': True}
                elif path == '/crumbIssuer/api/json':
                    value = {'crumbRequestField': 'crumb', 'crumb': SECRET}
                else:
                    if invalid_response:
                        return io.BytesIO(('PRIVATE ERROR ' + SECRET).encode())
                    value = report
                return io.BytesIO(json.dumps(value).encode())

            opener = MagicMock()
            opener.open.side_effect = endpoint
            playwright = MagicMock()
            playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_page.return_value.evaluate.return_value = {'name': 'admin'}
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch('subprocess.run', side_effect=command), \
                    patch('urllib.request.build_opener', return_value=opener), \
                    patch('playwright.sync_api.sync_playwright', playwright), \
                    patch.object(sys, 'argv', [str(SCRIPT), str(root)] + (['--connected-agents'] if connected_agents else [])), redirect_stdout(stdout), redirect_stderr(stderr):
                status = 0
                try:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
                except SystemExit as result:
                    status = result.code
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
            self.assertEqual(status, 1 if invalid_response or changed_admin or offline_agent else 0)
            self.assertEqual((root / 'runtime-acceptance.json').exists(), not (invalid_response or changed_admin or offline_agent))

    def test_success_does_not_print_credentials(self):
        self.invoke()

    def test_private_script_error_response_is_suppressed(self):
        self.invoke(invalid_response=True)

    def test_admin_hash_change_cannot_pass(self):
        self.invoke(changed_admin=True)

    def test_online_agents_preserve_execution_hold_and_current_admin(self):
        self.invoke(connected_agents=True)

    def test_offline_agents_cannot_pass_connected_acceptance(self):
        self.invoke(connected_agents=True, offline_agent=True)


if __name__ == '__main__':
    unittest.main()
