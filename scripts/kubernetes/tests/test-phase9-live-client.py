"""Check existing-admin authentication without exposing fixture credentials."""
from contextlib import redirect_stdout, redirect_stderr
import base64
import io
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'phase9-live-cycle.py'
MODULE = runpy.run_path(str(SCRIPT))
SECRET = 'FAKE-ADMIN-PASSWORD-PHASE9-ONLY'


class LiveClientTests(unittest.TestCase):
    def test_uses_only_nonprod_existing_login_and_never_prints_it(self):
        requests = []
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        class Opener:
            def open(self, request, **kwargs):
                requests.append(request)
                data = {'name': 'admin'} if request.full_url.endswith('/whoAmI/api/json') else {'ok': True}
                return Response(json.dumps(data).encode())
        secret = {'data': {'jenkins-admin-password': base64.b64encode(SECRET.encode()).decode()}}
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, json.dumps(secret).encode(), b'')) as kube, \
             patch('urllib.request.build_opener', return_value=Opener()), redirect_stdout(stdout), redirect_stderr(stderr):
            request = MODULE['client']()
            self.assertEqual(json.loads(request('/api/json')), {'ok': True})
        arguments = kube.call_args.args[0]
        self.assertIn('--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'), arguments)
        self.assertIn('jenkins-foundation-login', arguments)
        self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
        expected = 'Basic ' + base64.b64encode(('admin:' + SECRET).encode()).decode()
        self.assertTrue(all(r.get_header('Authorization') == expected for r in requests))
        self.assertTrue(all(r.full_url.startswith('http://192.168.77.16:8085/') for r in requests))


class ScriptResultTests(unittest.TestCase):
    def test_completed_script_preserves_only_its_actual_output(self):
        helper = MODULE['script'].__globals__['HELPER']
        with patch.dict(helper, {'script': lambda request, text: b'{"ok":true}\n\nPHASE9_SCRIPT_COMPLETED\n'}):
            self.assertEqual(MODULE['script'](object(), "println 'ok'"), b'{"ok":true}\n')

    def test_http_200_script_failure_is_rejected_without_diagnostic_leak(self):
        helper = MODULE['script'].__globals__['HELPER']
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(helper, {'script': lambda request, text: ('Assertion failed: ' + SECRET).encode()}), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(RuntimeError) as error:
                MODULE['script'](object(), 'assert false')
        self.assertNotIn(SECRET, str(error.exception) + stdout.getvalue() + stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
