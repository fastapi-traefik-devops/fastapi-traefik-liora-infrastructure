#!/usr/bin/env python3
"""Ensure agent preparation preserves operator Secrets and requires an execution hold."""

import base64
import io
import json
from pathlib import Path
import runpy
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
