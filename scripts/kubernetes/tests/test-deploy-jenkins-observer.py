#!/usr/bin/env python3
"""Ensure the observer installer keeps its pin, Secret source and immutable bundle."""

import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy-jenkins-observer.py'
ROOT = SCRIPT.parents[2]


def rendered():
    output = subprocess.check_output(['kubectl', 'kustomize', str(ROOT / 'kubernetes/platform/nonprod/jenkins/acceptance')])
    return list(yaml.safe_load_all(output))


def bundle(name):
    return {'kind': 'ConfigMap', 'metadata': {'name': name}, 'data': {'stage_acceptance.py': 'reviewed\n'}}


class ObserverDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path(str(SCRIPT))
        source = runpy.run_path(str(ROOT / 'scripts/kubernetes/prepare-jenkins-publisher-source.py'))
        self.pinned = 'jenkins-acceptance-ci-' + source['OBSERVER_SOURCE_COMMIT'][:12]

    def test_manifest_matches_the_observer_bundle_pin(self):
        deployment = self.module['check_resources'](rendered(), bundle(self.pinned))
        self.assertEqual(deployment['metadata']['name'], 'stage-observer')

    def test_mismatched_bundle_pin_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.module['check_resources'](rendered(), bundle('jenkins-acceptance-ci-000000000000'))

    def test_secret_from_git_is_rejected(self):
        resources = rendered() + [{'kind': 'Secret', 'metadata': {'name': 'stage-observer-connection'}}]
        with self.assertRaises(RuntimeError):
            self.module['check_resources'](resources, bundle(self.pinned))

    def test_existing_different_bundle_is_preserved(self):
        globals_ = self.module['install_bundle'].__globals__
        existing = json.dumps({'data': {'stage_acceptance.py': 'other\n'}}).encode()
        with patch.dict(globals_, {'run': lambda *args: existing, 'apply': MagicMock()}):
            with self.assertRaises(RuntimeError):
                self.module['install_bundle'](bundle(self.pinned))
            globals_['apply'].assert_not_called()

    def test_matching_bundle_is_not_reapplied(self):
        globals_ = self.module['install_bundle'].__globals__
        existing = json.dumps(bundle(self.pinned)).encode()
        with patch.dict(globals_, {'run': lambda *args: existing, 'apply': MagicMock()}):
            self.module['install_bundle'](bundle(self.pinned))
            globals_['apply'].assert_not_called()

    def test_missing_bundle_is_created(self):
        globals_ = self.module['install_bundle'].__globals__
        with patch.dict(globals_, {'run': lambda *args: b'', 'apply': MagicMock()}):
            self.module['install_bundle'](bundle(self.pinned))
            globals_['apply'].assert_called_once()


if __name__ == '__main__':
    unittest.main()
