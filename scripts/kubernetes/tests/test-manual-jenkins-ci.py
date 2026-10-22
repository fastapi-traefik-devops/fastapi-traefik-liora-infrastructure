#!/usr/bin/env python3
"""Check one-shot scheduling and hold restoration without Jenkins or Kubernetes."""
import json
import hashlib
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'manual-jenkins-ci.py'


class ManualCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path(str(SCRIPT))
        self.env = self.module['execute'].__globals__
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.state = {'configs': {'legacy': 'hash'}, 'users': {'admin': 'hash'},
                      'jobs': {'legacy': {'disabled': True, 'builds': 139, 'triggers': 0}},
                      'quiet': True, 'queue': 0, 'running': 0}
        for name, data in [('baseline.json', self.state),
                           ('receipt.json', {'sha': 'a' * 40, 'bundle': '/fake/source.bundle',
                                               'definition_sha256': hashlib.sha256(b'fixture').hexdigest()})]:
            (self.directory / name).write_text(json.dumps(data))

    def execute(self, fail_post=False):
        request = Mock(side_effect=lambda path: b'<flow-definition><definition><script>fixture</script></definition></flow-definition>'
                       if path.endswith('config.xml') else json.dumps(
                           {'builds': [{'number': 1, 'building': False, 'result': 'FAILURE'}]}).encode())
        post = Mock(side_effect=OSError('ambiguous response') if fail_post else None)
        hold = Mock()
        with patch.dict(self.env, {'client': lambda: request, 'inspect': lambda _: self.state,
                                 'script': Mock(), 'post': post, 'hold': hold}):
            if fail_post:
                with self.assertRaises(OSError):
                    self.module['execute'](self.directory)
            else:
                self.module['execute'](self.directory)
        post.assert_called_once()
        hold.assert_called_once_with(request)

    def test_finished_failed_build_is_not_retried(self):
        self.execute()
        self.assertTrue((self.directory / 'request-boundary.json').exists())

    def test_ambiguous_post_is_not_retried_and_restores_hold(self):
        self.execute(fail_post=True)
        self.assertFalse((self.directory / 'build-result.json').exists())

    def test_existing_request_boundary_prevents_activation(self):
        (self.directory / 'request-boundary.json').write_text('{}')
        activate = Mock()
        with patch.dict(self.env, {'client': lambda: lambda _: b'<flow-definition><definition><script>fixture</script></definition></flow-definition>',
                                 'inspect': lambda _: self.state, 'script': activate}):
            with self.assertRaises(FileExistsError):
                self.module['execute'](self.directory)
        activate.assert_not_called()

    def test_modified_imported_configuration_blocks_activation(self):
        changed = {**self.state, 'configs': {'legacy': 'different'}}
        activate = Mock()
        with patch.dict(self.env, {'client': Mock(), 'inspect': lambda _: changed, 'script': activate}):
            with self.assertRaisesRegex(RuntimeError, 'configuration or users changed'):
                self.module['execute'](self.directory)
        activate.assert_not_called()
        self.assertFalse((self.directory / 'request-boundary.json').exists())


if __name__ == '__main__':
    unittest.main()
