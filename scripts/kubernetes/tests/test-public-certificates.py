"""Check certificate scope and credential-safe provisioning failures."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('dns_bootstrap', ROOT / 'scripts/kubernetes/bootstrap-cloudflare-dns.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CertificateTests(unittest.TestCase):
    def test_independent_certificates_use_existing_secret_and_exact_host(self):
        for env in ['dev', 'stage', 'prod']:
            obj = yaml.safe_load((ROOT / 'kubernetes/apps/liora/overlays' / env / 'certificate.yaml').read_text())
            self.assertEqual(obj['metadata']['namespace'], 'app-' + env)
            self.assertEqual(obj['spec']['secretName'], 'app-tls')
            self.assertEqual(obj['spec']['dnsNames'], ['liora.aprt.info' if env == 'prod' else env + '.liora.aprt.info'])
            self.assertEqual(obj['spec']['privateKey']['rotationPolicy'], 'Always')

    def test_dns_solver_is_restricted_to_exact_application_names(self):
        obj = yaml.safe_load((ROOT / 'kubernetes/platform/public-certificates/issuer.yaml').read_text())
        solvers = obj['spec']['acme']['solvers']
        self.assertEqual(len(solvers), 1)
        self.assertEqual(solvers[0]['selector'], {'dnsNames': ['dev.liora.aprt.info', 'stage.liora.aprt.info', 'liora.aprt.info']})

    def test_controller_supports_acme_and_existing_internal_tls(self):
        import subprocess
        objects = yaml.safe_load_all(subprocess.check_output(['kubectl', 'kustomize', str(ROOT / 'kubernetes/platform/cert-manager')]))
        controller = next(x for x in objects if x.get('kind') == 'Deployment' and x['metadata']['name'] == 'cert-manager')
        args = controller['spec']['template']['spec']['containers'][0]['args']
        self.assertFalse(any(x.startswith(('--controllers=', '--namespace=')) for x in args))
        self.assertIn('--cluster-resource-namespace=$(POD_NAMESPACE)', args)

    def test_secret_and_api_errors_do_not_leak_token(self):
        fixture = 'fixture-DNS-token-never-print-123456789'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'token'
            path.write_text(fixture)
            path.chmod(0o600)
            for api_error in [ValueError(fixture), RuntimeError(fixture)]:
                output = io.StringIO()
                with patch('sys.argv', ['bootstrap', '--token-file', str(path)]), patch.object(MODULE, 'check_zone', side_effect=api_error), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    self.assertEqual(MODULE.main(), 1)
                self.assertNotIn(fixture, output.getvalue())

    def test_token_file_requires_private_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'token'
            path.write_text('fake-test-token')
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                MODULE.read_token(path)
            path.chmod(0o600)
            link = Path(tmp) / 'link'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                MODULE.read_token(link)

    def test_provision_uses_stdin_and_checks_cluster(self):
        from types import SimpleNamespace
        fixture = 'fixture-DNS-token-never-print-123456789'
        with patch.object(MODULE.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0, stdout='https://192.168.77.11:6443'), SimpleNamespace(returncode=0)]) as run:
            MODULE.provision(fixture, Path('/private/config'), 'https://192.168.77.11:6443')
            args, kwargs = run.call_args
            self.assertNotIn(fixture, str(args))
            obj = json.loads(kwargs['input'])
            self.assertEqual(obj['stringData']['api-token'], fixture)
            self.assertIn('--server-side', args[0])
        with patch.object(MODULE.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='https://wrong-cluster')) as run:
            with self.assertRaises(ValueError):
                MODULE.provision(fixture, Path('/private/config'), 'https://192.168.77.11:6443')
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
