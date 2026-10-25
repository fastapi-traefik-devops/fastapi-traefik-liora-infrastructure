#!/usr/bin/env python3
"""Ensure agent preparation preserves operator Secrets and requires an execution hold."""

import base64
import io
import json
from pathlib import Path
import runpy
import subprocess

import yaml
import unittest
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy-jenkins-agents.py'
SECRET = 'FAKE-INBOUND-SECRET-ONLY-551b'


class AgentDeploymentTests(unittest.TestCase):
    def test_existing_different_secret_is_never_overwritten(self):
        module = runpy.run_path(str(SCRIPT))
        run = module['copy_secret'].__globals__
        original = json.dumps({'type': 'Opaque', 'data': {'agent-secret': SECRET}}).encode()
        with patch.dict(run, {'run': lambda *args: original, 'apply': MagicMock()}):
            with self.assertRaises(RuntimeError):
                module['copy_secret']({'type': 'Opaque', 'data': {'agent-secret': 'different'}}, 'jenkins-ci', 'jenkins-inbound')
            run['apply'].assert_not_called()

    def test_matching_secret_is_not_rewritten(self):
        module = runpy.run_path(str(SCRIPT))
        globals_ = module['copy_secret'].__globals__
        secret = {'type': 'Opaque', 'data': {'agent-secret': SECRET}}
        with patch.dict(globals_, {'run': lambda *args: json.dumps(secret).encode(), 'apply': MagicMock()}):
            module['copy_secret'](secret, 'jenkins-ci', 'jenkins-inbound')
            globals_['apply'].assert_not_called()

    def test_fresh_and_restored_homes_keep_pins_storage_and_startup_hold(self):
        module = runpy.run_path(str(SCRIPT))
        root = SCRIPT.parents[2]
        rendered = subprocess.check_output(['kubectl', 'kustomize', str(root / 'kubernetes/platform/nonprod/jenkins/agents')])
        base = list(yaml.safe_load_all((root / 'kubernetes/platform/nonprod/jenkins/base/foundation.yaml').read_text()))
        for home in ('jenkins-home', 'accepted-current-home'):
            resources = list(yaml.safe_load_all(rendered))
            deployment = json.loads(json.dumps(next(r for r in base if r['kind'] == 'Deployment')))
            next(v for v in deployment['spec']['template']['spec']['volumes'] if v['name'] == 'home')['persistentVolumeClaim']['claimName'] = home
            original_image = deployment['spec']['template']['spec']['containers'][0]['image']
            prepared, config_name = module['configure_controller'](resources, deployment)
            controller = next(r for r in prepared if r['kind'] == 'Deployment' and r['metadata']['namespace'] == 'jenkins')
            self.assertEqual(next(v for v in controller['spec']['template']['spec']['volumes'] if v['name'] == 'home')['persistentVolumeClaim']['claimName'], home)
            self.assertEqual(controller['spec']['template']['spec']['containers'][0]['image'], original_image)
            configs = [r for r in prepared if r['kind'] == 'ConfigMap' and r['metadata']['name'] == config_name]
            self.assertEqual(len(configs), 1)
            self.assertIn('doQuietDown', configs[0]['data']['agent-hold.groovy'])
            casc = yaml.safe_load(configs[0]['data']['jenkins.yaml'])
            self.assertNotIn('users', casc['jenkins']['securityRealm']['local'])
            self.assertEqual(casc['jenkins']['numExecutors'], 0)
            self.assertFalse(any(r['kind'] == 'PersistentVolumeClaim' and r['metadata']['namespace'] == 'jenkins' for r in prepared))

    def hold(self, quiet=True, disabled=True):
        module = runpy.run_path(str(SCRIPT))
        globals_ = module['held_request'].__globals__
        secret = json.dumps({'data': {'jenkins-admin-password': base64.b64encode(SECRET.encode()).decode()}}).encode()
        report = {'quiet': quiet, 'executors': 0, 'queue': 0, 'jobs_disabled': disabled, 'running': 0}
        responses = [io.BytesIO(json.dumps(value).encode()) for value in
                     [{'name': 'admin'}, {'crumbRequestField': 'crumb', 'crumb': SECRET}, report]]
        opener = MagicMock()
        opener.open.side_effect = responses
        with patch.dict(globals_, {'run': lambda *args: secret}), \
                patch('urllib.request.build_opener', return_value=opener):
            if quiet and disabled:
                self.assertTrue(callable(module['held_request']()))
            else:
                with self.assertRaises(RuntimeError):
                    module['held_request']()
        self.assertEqual(opener.open.call_count, 3)
        script = opener.open.call_args.args[0].data.decode()
        self.assertNotIn('scheduleBuild', script)
        self.assertNotIn('setDisabled', script)

    def test_held_controller_can_prepare_connections(self):
        self.hold()

    def test_active_controller_blocks_preparation(self):
        self.hold(quiet=False)

    def test_enabled_jobs_block_preparation(self):
        self.hold(disabled=False)


if __name__ == '__main__':
    unittest.main()
