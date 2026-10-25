#!/usr/bin/env python3
"""Generated, isolated recovery fixtures; no network or real credentials required."""
import copy
import datetime
import importlib.util
import io
import os
from pathlib import Path
import secrets
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
import sys
sys.dont_write_bytecode = True
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('checker', HERE / 'check_credentials.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CredentialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='liora-credential-tests-')
        cls.root = Path(cls.fixture.name)
        key = ed25519.Ed25519PrivateKey.generate()
        cls.private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                       serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
        controller = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'fixture-controller')])
        now = datetime.datetime.now(datetime.timezone.utc)
        cls.cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(controller.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
                    .not_valid_after(now + datetime.timedelta(days=1)).sign(controller, hashes.SHA256())
                    .public_bytes(serialization.Encoding.PEM).decode())
        cls.pem = controller.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()).decode()
        cls.env = {
            'TF_VAR_pm_endpoint': 'https://192.0.2.1:8006/', 'TF_VAR_pm_node': 'fixture-node',
            'TF_VAR_pm_api_token': 'fixture@pam!fixture-token=' + str(__import__('uuid').uuid4()),
            'DISK_STORAGE': 'fixture.storage', 'TF_VAR_cloud_init_datastore_id': 'fixture.storage',
            'TAILSCALE_API_KEY': 'tskey-api-' + secrets.token_urlsafe(24), 'TAILSCALE_TAILNET': '-',
            'GHCR_REGISTRY': 'ghcr.io', 'GHCR_USERNAME': 'fixture-operator',
            'GHCR_TOKEN': 'ghp_' + ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(36)),
        }
        cls.data = {'schema_version': 1, 'kubernetes': {'nonprod': {'sealed_secrets_controller_keys': [
            {'secret_name': 'fixture-controller', 'tls_crt_pem': cls.cert, 'tls_key_pem': cls.pem}]}},
            'application_credentials': {}}
        cls.canaries = [cls.env['TF_VAR_pm_api_token'], cls.env['GHCR_TOKEN'], cls.env['TAILSCALE_API_KEY'],
                        cls.pem.splitlines()[1], cls.cert.splitlines()[1], cls.private.decode().splitlines()[1],
                        cls.public.decode().split()[1]]
        for env in ('dev', 'stage', 'prod'):
            password = secrets.token_urlsafe(24)
            signing = secrets.token_urlsafe(32)
            db = secrets.token_urlsafe(32)
            smtp = '' if env == 'dev' else secrets.token_urlsafe(24)
            cls.canaries += [password, signing, db] + ([smtp] if smtp else [])
            cls.data['application_credentials'][env] = {
                'namespace': 'app-' + env, 'first_superuser': 'admin007@liora.aprt.info',
                'backend-secrets': {'SECRET_KEY': signing, 'FIRST_SUPERUSER_PASSWORD': password,
                                    'POSTGRES_PASSWORD': db, 'SMTP_PASSWORD': smtp},
                'db-secrets': {'POSTGRES_PASSWORD': db}}

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.directory = self.root / self.id().split('.')[-1]
        self.directory.mkdir()
        self.env_values = dict(self.env)
        self.yaml_values = copy.deepcopy(self.data)
        self.write()

    def write(self):
        env = '\n'.join(f"export {k}='{v}'" for k, v in self.env_values.items()) + '\n'
        (self.directory / '.env').write_text(env)
        (self.directory / 'recovery.yaml').write_text(yaml.safe_dump(self.yaml_values))
        (self.directory / 'LIORA-id_ed25519').write_bytes(self.private)
        (self.directory / 'LIORA-id_ed25519.pub').write_bytes(self.public)
        for path in self.directory.iterdir():
            path.chmod(0o600)

    def run_check(self, args=('--offline',), expected=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'RECOVERY_DIR': str(self.directory)}), redirect_stdout(stdout), redirect_stderr(stderr):
            status = checker.main(list(args))
        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, expected, output)
        for value in self.canaries:
            self.assertNotIn(value, output)
        return output

    def test_database_backup_fields_and_secret_safe_errors(self):
        account='a'*32;access='b'*32;secret='c'*64;token='fixture-r2-api-token-must-stay-private'
        self.canaries = list(self.canaries) + [access, secret, token]
        backup={'account_id':account,'endpoint':'https://'+account+'.r2.cloudflarestorage.com',
                'jurisdiction':'default','region':'auto','bucket':'liora-backup',
                'access_key_id':access,'secret_access_key':secret,'api_token':token}
        self.yaml_values['database_backups']=backup;self.write();self.run_check()
        for key in backup:
            with self.subTest(key=key):
                original=backup[key];backup[key]='invalid-fixture-value';self.write()
                self.run_check(expected=0 if key=='api_token' else 1)
                backup[key]=original
        backup['obsolete_backup_field']='fixture-hidden-value';self.write()
        self.assertIn('obsolete_backup_field',self.run_check())
        self.run_check(args=('--offline','--strict-warnings'),expected=1)

    def test_generated_backup_coordinator_schema(self):
        import base64, json
        account='a'*32
        backup={'account_id':account,'endpoint':'https://'+account+'.r2.cloudflarestorage.com',
                'jurisdiction':'default','region':'auto','bucket':'liora-backup',
                'access_key_id':'b'*32,'secret_access_key':'c'*64}
        encode=lambda value:base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b'=').decode()
        token=encode({'alg':'RS256'})+'.'+encode({'sub':'system:serviceaccount:cnpg-system:backup-coordinator'})+'.fixture-signature'
        self.canaries=list(self.canaries)+[backup['access_key_id'],backup['secret_access_key'],token]
        self.yaml_values['database_backups']=backup;self.write()
        profile=lambda vip,admin:{'server':'https://'+vip+':6443','alertmanager':'http://'+admin+':9093','token':token,'ca_pem':self.cert}
        data={'version':1,'state_dir':'/var/lib/liora-backups','listen':'192.168.77.250',
              'r2':{k:backup[k] for k in ['endpoint','bucket','access_key_id','secret_access_key']},
              'clusters':{'nonprod':profile('192.168.77.11','192.168.77.16'),'prod':profile('192.168.77.12','192.168.77.17')}}
        path=self.directory/'backup-coordinator.json'
        def write():path.write_text(json.dumps(data));path.chmod(0o600)
        write();self.run_check()
        for key in ['server','alertmanager','token','ca_pem']:
            original=data['clusters']['prod'][key];data['clusters']['prod'][key]='fixture-invalid-secret';write();self.run_check(expected=1);data['clusters']['prod'][key]=original
        data['clusters']['prod']['obsolete']='fixture-hidden-value';write();self.assertIn('obsolete',self.run_check())
        self.run_check(args=('--offline','--strict-warnings'),expected=1)

    def test_complete_success_and_wrapper(self):
        self.run_check()
        env = dict(os.environ, RECOVERY_DIR=str(self.directory), RECOVERY_PYTHON=sys.executable)
        result = subprocess.run(['bash', str(HERE / 'check_credentials.sh'), '--all', '--offline'],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in self.canaries:
            self.assertNotIn(value, result.stdout + result.stderr)

    def test_every_required_environment_variable(self):
        for key in self.env:
            with self.subTest(key=key):
                self.env_values = dict(self.env)
                del self.env_values[key]
                self.write()
                self.assertIn(key, self.run_check(expected=1))

    def test_environment_formats(self):
        bad = {'TF_VAR_pm_endpoint': ['http://192.0.2.1', 'https://user:pass@host/', 'https://host/path',
                                      'https://host:65536/', 'https://host:/', 'https://host/?x=1',
                                      'https://@host/', 'https://host/#', 'https://host/?'],
               'TF_VAR_pm_node': ['node_', '-node'],
               'TF_VAR_pm_api_token': ['user@pam!id=secret', 'u@p!id=00000000-0000-0000-0000-000000000000'],
               'DISK_STORAGE': ['a', '-disk', 'disk/one'],
               'TF_VAR_cloud_init_datastore_id': ['different'],
               'TAILSCALE_API_KEY': ['tskey-auth-fixture', 'tskey-api-'],
               'TAILSCALE_TAILNET': ['net/name', ''], 'GHCR_REGISTRY': ['docker.io'],
               'GHCR_USERNAME': ['a' * 40, '-user', 'user--name'],
               'GHCR_TOKEN': ['github_pat_' + 'a' * 50, 'ghp_' + 'a' * 35],
               'PROXMOX_PUBLIC_IP': ['256.0.0.1', 'host.example']}
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.env_values = dict(self.env, **{key: value})
                    self.write()
                    self.assertIn(key, self.run_check(expected=1))

    def test_missing_and_wrong_type_for_every_yaml_field(self):
        def paths(value, prefix=()):
            if isinstance(value, dict):
                for key, val in value.items():
                    yield prefix + (key,)
                    yield from paths(val, prefix + (key,))
            elif isinstance(value, list):
                for i, val in enumerate(value):
                    yield from paths(val, prefix + (i,))
        for path in paths(self.data):
            for mutation in ('missing', 'type'):
                with self.subTest(path=path, mutation=mutation):
                    self.yaml_values = copy.deepcopy(self.data)
                    parent = self.yaml_values
                    for key in path[:-1]:
                        parent = parent[key]
                    if mutation == 'missing':
                        del parent[path[-1]]
                    else:
                        parent[path[-1]] = False
                    self.write()
                    expected = 0 if path == ('kubernetes',) and mutation == 'missing' else 1
                    self.run_check(expected=expected)

    def test_password_boundaries_and_no_invented_secret_limits(self):
        for length in (7, 8, 40, 41):
            self.yaml_values = copy.deepcopy(self.data)
            self.yaml_values['application_credentials']['dev']['backend-secrets']['FIRST_SUPERUSER_PASSWORD'] = 'ü' * length
            self.write()
            self.run_check(expected=0 if 8 <= length <= 40 else 1)
        app = self.yaml_values['application_credentials']['dev']
        app['backend-secrets']['FIRST_SUPERUSER_PASSWORD'] = 'A' * 8
        app['backend-secrets']['SECRET_KEY'] = 'small'
        app['backend-secrets']['POSTGRES_PASSWORD'] = app['db-secrets']['POSTGRES_PASSWORD'] = 'p' * 1000
        app['backend-secrets']['SMTP_PASSWORD'] = ' ' + secrets.token_urlsafe(16) + '\n'
        self.write()
        self.assertIn('fewer than 32', self.run_check())
        self.run_check(('--offline', '--strict-warnings'), expected=1)

    def test_application_formats_and_password_equality(self):
        for key, value in [('namespace', 'app-wrong'), ('first_superuser', 'bad-email'),
                           ('first_superuser', 'other@liora.aprt.info')]:
            self.yaml_values = copy.deepcopy(self.data)
            self.yaml_values['application_credentials']['dev'][key] = value
            self.write()
            self.run_check(expected=1)
        self.yaml_values = copy.deepcopy(self.data)
        self.yaml_values['application_credentials']['stage']['db-secrets']['POSTGRES_PASSWORD'] += 'mismatch'
        self.write()
        self.run_check(expected=1)

    def test_current_yaml_does_not_require_controller_keys(self):
        del self.yaml_values['kubernetes']
        self.write()
        self.run_check()

    def test_unknown_locations_obsolete_names_and_preservation(self):
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        self.env_values['OLD_API_TOKEN'] = canary
        self.env_values['POSTGRES_PASSWORD'] = canary
        self.yaml_values['application_credentials']['stage']['backend-secrets']['OLD_SECRET'] = canary
        self.yaml_values['kubernetes']['nonprod']['sealed_secrets_controller_keys'][0]['old_key'] = canary
        self.yaml_values['schema_obsolete'] = {'nested_obsolete': canary}
        self.write()
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        output = self.run_check()
        for name in ('OLD_API_TOKEN', 'POSTGRES_PASSWORD', 'OLD_SECRET', 'old_key', 'schema_obsolete', 'nested_obsolete'):
            self.assertIn(name, output)
        self.assertIn('recovery/.env:', output)
        self.assertIn('recovery/recovery.yaml:', output)
        self.run_check(('--offline', '--strict-warnings'), expected=1)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_safe_env_parser_and_errors_do_not_execute_or_echo(self):
        path = self.directory / '.env'
        original = path.read_text()
        sentinel = self.directory / 'executed'
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        for line in [f'BAD=$(touch {sentinel}; echo {canary})', f'BAD=`echo {canary}`',
                     f'BAD="{canary}', f'echo {canary}', f'GHCR_TOKEN={canary}',
                     'BAD=${NOT_DEFINED}', 'BAD=${HOME}', 'BAD=${HOME:-fallback}']:
            path.write_text(original + line + '\n')
            self.run_check(expected=1)
            self.assertFalse(sentinel.exists())
        path.write_text(original.replace("export TF_VAR_cloud_init_datastore_id='fixture.storage'",
                                         'export TF_VAR_cloud_init_datastore_id="$DISK_STORAGE"') + "EXTRA='$(literal)' # comment\n")
        self.run_check()

    def test_yaml_invalid_duplicate_alias_and_unknown_tags_are_redacted(self):
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        for content in [f'schema_version: [{canary}', f'schema_version: 1\nschema_version: {canary}',
                        f'schema_version: 1\nx: &a [{canary}]\ny: *a', f'!!python/object:{canary} {{}}',
                        'true: bad']:
            (self.directory / 'recovery.yaml').write_text(content)
            self.run_check(expected=1)

    def test_cert_ssh_and_permissions(self):
        self.yaml_values['kubernetes']['nonprod']['sealed_secrets_controller_keys'][0]['tls_key_pem'] = self.private.decode()
        self.write()
        self.run_check(expected=1)
        self.yaml_values = copy.deepcopy(self.data)
        self.write()
        other = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.OpenSSH,
                                                                             serialization.PublicFormat.OpenSSH)
        (self.directory / 'LIORA-id_ed25519.pub').write_bytes(other)
        self.run_check(expected=1)
        self.write()
        (self.directory / '.env').chmod(0o644)
        self.run_check(expected=1)

    def test_certificate_expiry_warns_and_mismatch_fails(self):
        key = serialization.load_pem_private_key(self.pem.encode(), password=None)
        now = datetime.datetime.now(datetime.timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'fixture-expired')])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=30))
                .not_valid_after(now - datetime.timedelta(days=1)).sign(key, hashes.SHA256())
                .public_bytes(serialization.Encoding.PEM).decode())
        item = self.yaml_values['kubernetes']['nonprod']['sealed_secrets_controller_keys'][0]
        item['tls_crt_pem'] = cert
        self.write()
        self.assertIn('outside its validity period', self.run_check())
        self.run_check(('--offline', '--strict-warnings'), expected=1)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        item['tls_key_pem'] = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                serialization.NoEncryption()).decode()
        self.canaries = self.canaries + [item['tls_key_pem'].splitlines()[1]]
        self.write()
        self.run_check(expected=1)

    def test_optional_tokens_and_tailscale_scope(self):
        for name in ('k3s-dev-stage.token', 'k3s-prod.token'):
            path = self.directory / name
            path.write_text('a' * 64 + '\n')
            path.chmod(0o600)
            self.run_check()
            path.write_text('a' * 63)
            self.run_check(expected=1)
            path.unlink()
        for key in checker.GHCR:
            del self.env_values[key]
        self.write()
        (self.directory / 'recovery.yaml').unlink()
        self.run_check(('--tailscale', '--offline'))
        self.run_check(expected=1)

    def test_live_probe_redacts_bodies_and_exceptions(self):
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        for code in (200, 401, 403, 404, 302, 500):
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.status = code
            response.read.return_value = canary.encode()
            with patch.object(checker.urllib.request.OpenerDirector, 'open', return_value=response):
                output = self.run_check((), expected=0 if code == 200 else 1)
                self.assertIn(str(code), output)
        with patch.object(checker.urllib.request.OpenerDirector, 'open', side_effect=ValueError(canary)):
            self.run_check((), expected=1)
        error = checker.urllib.error.HTTPError('https://' + canary, 401, canary, {}, io.BytesIO(canary.encode()))
        with patch.object(checker.urllib.request.OpenerDirector, 'open', side_effect=error):
            self.run_check((), expected=1)

    def test_secret_name_and_secret_value_boundaries(self):
        for name in ('-bad', 'bad.', 'Bad', 'a..b', 'a' * 254):
            self.yaml_values = copy.deepcopy(self.data)
            self.yaml_values['kubernetes']['nonprod']['sealed_secrets_controller_keys'][0]['secret_name'] = name
            self.write()
            self.run_check(expected=1)
        self.yaml_values = copy.deepcopy(self.data)
        self.yaml_values['kubernetes']['nonprod']['sealed_secrets_controller_keys'][0]['secret_name'] = 'a' * 253
        self.write()
        self.run_check()
        for key in ('SECRET_KEY', 'FIRST_SUPERUSER_PASSWORD', 'POSTGRES_PASSWORD', 'SMTP_PASSWORD'):
            for value in ('bad\0value', '\ud800', 'REPLACE_WITH_SECRET', None):
                self.yaml_values = copy.deepcopy(self.data)
                self.yaml_values['application_credentials']['prod']['backend-secrets'][key] = value
                self.write()
                self.run_check(expected=1)

    def test_no_environment_fallback(self):
        del self.env_values['GHCR_TOKEN']
        self.write()
        with patch.dict(os.environ, {'GHCR_TOKEN': self.env['GHCR_TOKEN']}):
            self.run_check(expected=1)

    def test_real_https_probe_and_redirect_rejection(self):
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        calls = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            status_code = 200

            def log_message(self, *args):
                pass

            def do_GET(self):
                calls.append((self.path, self.headers.get('Authorization') ==
                              'PVEAPIToken=' + owner.env['TF_VAR_pm_api_token']))
                self.send_response(self.status_code)
                if self.status_code == 302:
                    self.send_header('Location', '/redirected/' + canary)
                self.end_headers()
                self.wfile.write(canary.encode())

        cert_file, key_file = self.directory / 'fixture.crt', self.directory / 'fixture.key'
        cert_file.write_text(self.cert)
        key_file.write_text(self.pem)
        cert_file.chmod(0o600)
        key_file.chmod(0o600)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        server = HTTPServer(('127.0.0.1', 0), Handler)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.env_values['TF_VAR_pm_endpoint'] = 'https://127.0.0.1:' + str(server.server_port)
            self.write()
            for status in (200, 401, 302):
                Handler.status_code = status
                self.run_check((), expected=0 if status == 200 else 1)
            self.assertEqual(calls, [('/api2/json/nodes/fixture-node/qemu/9013/config', True)] * 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_dependency_and_interpreter_exit_status(self):
        result = subprocess.run([sys.executable, '-I', '-S', str(HERE / 'check_credentials.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('requirements.txt', result.stderr)
        env = dict(os.environ, RECOVERY_PYTHON='/nonexistent-recovery-python')
        result = subprocess.run(['bash', str(HERE / 'check_credentials.sh')], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python 3 is required', result.stderr)

    def test_usage_redacts_arguments(self):
        canary = secrets.token_urlsafe(27)
        self.canaries = self.canaries + [canary]
        self.run_check((canary,), expected=2)


if __name__ == '__main__':
    unittest.main()
