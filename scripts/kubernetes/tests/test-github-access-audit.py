"""A read-only permissions audit never logs the stored key or temporary token."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / 'check-jenkins-github-access.py'
MODULE = runpy.run_path(str(SCRIPT))
SECRET = 'FIXTURE-PRIVATE-KEY-NOT-REAL'
TOKEN = 'FIXTURE-INSTALLATION-TOKEN'


class AuditTests(unittest.TestCase):
    def test_success_and_forbidden_protection_never_print_secret_values(self):
        class Key:
            def sign(self, *args): return b'fixture-signature'
        class Response(io.BytesIO):
            def __init__(self, status, value):
                super().__init__(json.dumps(value).encode())
                self.status = status
        def api(request, **kwargs):
            url = request.full_url
            if url.endswith('/branches/main/protection'):
                raise urllib.error.HTTPError(url, 403, SECRET, {}, None)
            if url.endswith('/installation/token'): return Response(204, None)
            if url.endswith('/access_tokens'): return Response(201, {'token': TOKEN})
            if url.endswith('/installation'):
                return Response(200, {'id': 1, 'permissions': {'contents': 'write'}, 'repository_selection': 'selected'})
            return Response(200, [])
        credentials = {name: {'id': '123', 'key': SECRET} for name in ['github-ci-app', 'gitops-app']}
        helper = {'client': lambda: object(), 'inspect': lambda request: {'held': True},
                  'script': lambda *args: json.dumps(credentials)}
        with tempfile.TemporaryDirectory() as directory:
            # Preserve the script's root calculation while redirecting its output only.
            fake = Path(directory) / 'scripts/kubernetes/audit.py'
            fake.parent.mkdir(parents=True)
            output = io.StringIO()
            main = MODULE['main']
            with patch.dict(main.__globals__, __file__=str(fake)), \
                 patch('runpy.run_path', return_value=helper), \
                 patch('urllib.request.urlopen', side_effect=api), \
                 patch.object(MODULE['serialization'], 'load_pem_private_key', return_value=Key()), \
                 redirect_stdout(output):
                self.assertEqual(main(), 0)
            serialized = output.getvalue()
            self.assertNotIn(SECRET, serialized)
            self.assertNotIn(TOKEN, serialized)
            result = json.loads(serialized)
            self.assertEqual(result['branch_audit']['classic_protection']['status'], 403)
            self.assertEqual(result['branch_audit']['temporary_token_revocation_status'], 204)
            saved = Path(directory) / '.local-work/private/phase9/github-app-access-current.json'
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(SECRET, saved.read_text())
            self.assertNotIn(TOKEN, saved.read_text())


if __name__ == '__main__':
    unittest.main()
