"""Regression checks for false success and wrong-target/output guards; no Docker calls."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import verify_local_lab as v


class VerifierTests(unittest.TestCase):
    def test_zero_replicas_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Zero replicas'):
            v.deployment_ready({'spec': {'replicas': 0}})

    def test_stale_generation_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'generation'):
            v.deployment_ready({'metadata': {'generation': 2}, 'status': {'observedGeneration': 1}})

    def test_partial_rollout_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'fully available'):
            v.deployment_ready({'metadata': {'generation': 2}, 'spec': {'replicas': 2},
                                'status': {'observedGeneration': 2, 'updatedReplicas': 1, 'availableReplicas': 2}})

    def test_wrong_cluster_short_circuits(self):
        calls = []
        def run(args):
            calls.append(args)
            return 'other-cluster'
        with self.assertRaisesRegex(RuntimeError, 'Wrong lab UID'):
            v.verify('running', run)
        self.assertEqual(len(calls), 1)

    def test_command_failure_not_masked(self):
        with patch.object(v.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'private diagnostic')):
            with self.assertRaisesRegex(RuntimeError, 'exit 1') as error:
                v.command(['docker', 'inspect'])
            self.assertNotIn('private diagnostic', str(error.exception))

    def test_running_original_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'stopped container'):
            v.verify('stopped', lambda _: 'running')

    def test_existing_output_preserved_before_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'keep'; marker.write_text('historical')
            with patch.object(sys, 'argv', ['verify', '--mode', 'stopped', '--output', directory]), patch.object(v, 'verify') as verify:
                with self.assertRaises(FileExistsError):
                    v.main()
                verify.assert_not_called()
            self.assertEqual(marker.read_text(), 'historical')

    def test_fail_result_is_recorded_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'new'
            with patch.object(sys, 'argv', ['verify', '--mode', 'running', '--output', str(out)]), patch.object(v, 'verify', side_effect=RuntimeError('wrong UID')), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v.main(), 1)
            self.assertEqual(json.loads((out/'verification.json').read_text())['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main(verbosity=2)
