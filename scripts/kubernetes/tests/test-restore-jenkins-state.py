#!/usr/bin/env python3
"""Exercise new-PVC transfer and fail-closed preconditions with fake cluster I/O."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / 'restore-jenkins-state.py'
ROOT = SCRIPT.parents[2]
SECRET = 'FAKE-CURRENT-ADMIN-ONLY-c9fee8'


def archive(path, files):
    with tarfile.open(fileobj=path, mode='w:gz') as target:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            target.addfile(member, io.BytesIO(data))


class RestoreTests(unittest.TestCase):
    def invoke(self, existing=False, bad_hash=False):
        module = runpy.run_path(str(SCRIPT))
        namespace = module['main'].__globals__
        events = []
        desired = next(item for item in yaml.safe_load_all((ROOT / 'kubernetes/platform/nonprod/jenkins/base/foundation.yaml').read_text())
                       if item['kind'] == 'Deployment')
        changes = yaml.safe_load((ROOT / 'kubernetes/platform/nonprod/jenkins/held/deployment-patch.yaml').read_text())['spec']['template']['spec']
        for patch_volume in changes['volumes']:
            for index, volume in enumerate(desired['spec']['template']['spec']['volumes']):
                if volume['name'] == patch_volume['name']:
                    desired['spec']['template']['spec']['volumes'][index] = patch_volume
        desired['spec']['template']['spec']['initContainers'] = changes['initContainers']
        deployment = json.loads(json.dumps(desired))
        for volume in deployment['spec']['template']['spec']['volumes']:
            if volume['name'] == 'home':
                volume['persistentVolumeClaim']['claimName'] = 'jenkins-home'
        files = {'config.xml': b'<hudson/>', 'secrets/master.key': b'FAKE-KEY'}
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        with tempfile.TemporaryDirectory(dir=ROOT / '.local-work') as directory:
            root = Path(directory)
            manifests = root / 'kubernetes/platform/nonprod/jenkins'
            manifests.mkdir(parents=True)
            (manifests / 'foundation.yaml').write_text(yaml.safe_dump(desired))
            lock = root / 'kubernetes/platform/upstream/infra/jenkins-host/plugins.lock.txt'
            lock.parent.mkdir(parents=True)
            lock.write_bytes(b'fake-plugin:1\n')

            source = root / 'source'
            source.mkdir()
            (source / 'manifest.json').write_text(json.dumps({'mode': 'stopped-preservation', 'consistent': True}))
            held = manifests / 'held'
            held.mkdir()
            (held / 'migration-hold.yaml').write_bytes((ROOT / 'kubernetes/platform/nonprod/jenkins/held/migration-hold.yaml').read_bytes())

            def run(arguments, data=None):
                events.append((arguments, data))
                if arguments[:3] == ['get', 'pvc', 'jenkins-home-restored']:
                    return b'existing' if existing else b''
                if arguments[:2] == ['get', 'pvc']:
                    return json.dumps({'spec': {'storageClassName': 'local-path', 'accessModes': ['ReadWriteOnce'], 'resources': {'requests': {'storage': '5Gi'}}}}).encode()
                if arguments[:2] == ['get', 'pod']:
                    return json.dumps({'spec': {'volumes': [{'name': 'restore', 'persistentVolumeClaim': {'claimName': 'jenkins-home-restored'}}]}}).encode()
                if arguments[:2] == ['get', 'deployment']:
                    return json.dumps(deployment).encode()
                if arguments[:2] == ['get', 'pods']:
                    return json.dumps({'items': [{'metadata': {'name': 'foundation'},
                        'status': {'phase': 'Running'}, 'spec': {'nodeName': 'fixture-node'}}]}).encode()
                if arguments[:1] == ['kustomize']:
                    return yaml.safe_dump(desired).encode()
                if 'cat /var/jenkins_home/users/*/config.xml' in arguments:
                    return ('<user><id>admin</id><passwordHash>' + SECRET + '</passwordHash></user>').encode()
                if '/usr/share/jenkins/ref/plugins.txt' in arguments:
                    return lock.read_bytes()
                if 'find' in arguments:
                    return ''.join(f'{("0" * 64 if bad_hash else digest)}  /restore/{name}\n'
                                   for name, digest in hashes.items()).encode()
                return b'{}'

            def stage(source, destination):
                destination.mkdir(mode=0o700)
                with (destination / 'inactive-home.tar.gz').open('wb') as stream:
                    archive(stream, files)

            def command(arguments, **kwargs):
                events.append((arguments, None))
                self.assertIn('--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'), arguments)
                self.assertEqual(arguments[2:4], ['-n', 'jenkins'])
                if 'stdout' in kwargs:
                    archive(kwargs['stdout'], files)
                return subprocess.CompletedProcess(arguments, 0, b'', b'')

            stdout = io.StringIO()
            with patch.dict(namespace, ROOT=root, run=run), \
                    patch('runpy.run_path', return_value={'stage': stage, 'digest': lambda path: hashlib.sha256(path.read_bytes()).hexdigest(), 'held_request': lambda: None}), \
                    patch('subprocess.run', side_effect=command), \
                    patch.object(sys, 'argv', [str(SCRIPT), str(root / 'source')]), redirect_stdout(stdout):
                if existing or bad_hash:
                    with self.assertRaises(RuntimeError):
                        module['main']()
                else:
                    module['main']()
            self.assertNotIn(SECRET, stdout.getvalue())
            self.assertFalse(any('delete' in arguments for arguments, _ in events))
            starts = [json.loads(data) for arguments, data in events
                      if arguments == ['apply', '-f', '-'] and data and json.loads(data).get('kind') == 'Deployment']
            if existing or bad_hash:
                self.assertFalse(starts)
            else:
                self.assertEqual(len(starts), 1)
                helper = next(json.loads(data) for arguments, data in events
                              if arguments == ['apply', '-f', '-'] and data and json.loads(data).get('kind') == 'Pod')
                volumes = helper['spec']['volumes']
                self.assertTrue(volumes[0]['persistentVolumeClaim']['readOnly'])
                self.assertEqual(volumes[0]['persistentVolumeClaim']['claimName'], 'jenkins-home')
                self.assertEqual(volumes[1]['persistentVolumeClaim']['claimName'], 'jenkins-home-restored')
                receipts = list(root.glob('.local-work/private/phase9/*/restore-receipt.json'))
                self.assertEqual(len(receipts), 1)
                self.assertTrue(json.loads(receipts[0].read_text())['runtime_acceptance_pending'])

    def test_backup_copies_stopped_home_read_only_and_leaves_controller_stopped(self):
        module = runpy.run_path(str(SCRIPT))
        events = []
        deployment = next(item for item in yaml.safe_load_all((ROOT / 'kubernetes/platform/nonprod/jenkins/base/foundation.yaml').read_text()) if item['kind'] == 'Deployment')
        files = {'config.xml': b'<hudson/>', 'secrets/master.key': SECRET.encode(), 'secrets/hudson.util.Secret': SECRET.encode()}
        def run(arguments, data=None):
            events.append((arguments, data))
            if arguments[:2] == ['get', 'deployment']:
                return json.dumps(deployment).encode()
            if arguments[:2] == ['get', 'pods']:
                return json.dumps({'items': [{'spec': {'nodeName': 'node-a'}}]}).encode()
            return b'{}'
        def command(arguments, **kwargs):
            archive(kwargs['stdout'], files)
            return subprocess.CompletedProcess(arguments, 0, b'', b'')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'backup'
            stdout = io.StringIO()
            with patch.dict(module['backup_home'].__globals__, run=run), patch('runpy.run_path', return_value={'held_request': lambda: None}), patch('subprocess.run', side_effect=command), redirect_stdout(stdout):
                module['backup_home'](target)
                with self.assertRaises(FileExistsError):
                    module['backup_home'](target)
            manifest = json.loads((target / 'manifest.json').read_text())
            self.assertTrue(manifest['consistent'])
            self.assertEqual(manifest['archives'][0]['sha256'], hashlib.sha256((target / 'home.tar.gz').read_bytes()).hexdigest())
            self.assertNotIn(SECRET, stdout.getvalue())
            pod = next(json.loads(data) for args, data in events if args == ['apply', '-f', '-'])
            self.assertTrue(pod['spec']['volumes'][0]['persistentVolumeClaim']['readOnly'])
            self.assertIn((['scale', 'deployment/jenkins', '--replicas=0'], None), events)
            self.assertFalse(any('--replicas=1' in args for args, _ in events))

    def test_resume_rejects_changed_target_before_hashing_or_start(self):
        module = runpy.run_path(str(SCRIPT))
        calls = []
        def run(arguments, data=None):
            calls.append(arguments)
            return json.dumps({'spec': {'volumes': [{'name': 'restore', 'persistentVolumeClaim': {'claimName': 'unrelated'}}]}}).encode()
        desired = {'spec': {'template': {'spec': {'volumes': [{'name': 'home', 'persistentVolumeClaim': {'claimName': 'accepted-target'}}]}}}}
        with patch.dict(module['finish_transfer'].__globals__, run=run):
            with self.assertRaises(RuntimeError):
                module['finish_transfer'](Path('/unused'), {'helper': 'transfer', 'deployment': desired})
        self.assertEqual(calls, [['get', 'pod', 'transfer', '-o', 'json']])

    def test_resume_checks_files_before_marking_complete(self):
        module = runpy.run_path(str(SCRIPT))
        calls = []
        desired = {'spec': {'template': {'spec': {'volumes': [{'name': 'home', 'persistentVolumeClaim': {'claimName': 'target'}}]}}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'expected-files.json').write_text(json.dumps({'config.xml': 'a' * 64}))
            def run(arguments, data=None):
                calls.append(arguments)
                if arguments[:2] == ['get', 'pod']:
                    return json.dumps({'spec': {'volumes': [{'name': 'restore', 'persistentVolumeClaim': {'claimName': 'target'}}]}}).encode()
                if 'find' in arguments:
                    return ('b' * 64 + '  /restore/config.xml\n').encode()
                raise AssertionError('Mismatch must prevent every later operation')
            with patch.dict(module['finish_transfer'].__globals__, run=run):
                with self.assertRaises(RuntimeError):
                    module['finish_transfer'](root, {'helper': 'transfer', 'deployment': desired})
            self.assertFalse((root / 'transfer-verified.json').exists())

    def test_restores_only_new_pvc_and_retains_read_only_foundation(self):
        self.invoke()

    def test_existing_migration_pvc_is_never_overwritten(self):
        self.invoke(existing=True)

    def test_hash_mismatch_prevents_target_start(self):
        self.invoke(bad_hash=True)


if __name__ == '__main__':
    unittest.main()
