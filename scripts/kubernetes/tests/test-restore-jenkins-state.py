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

            def run(arguments, data=None):
                events.append((arguments, data))
                if arguments[:3] == ['get', 'pvc', 'jenkins-home-migrated']:
                    return b'existing' if existing else b''
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

            def stage(source, destination, admin):
                self.assertEqual(admin.stat().st_mode & 0o777, 0o600)
                self.assertIn(SECRET, admin.read_text())
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
                    patch('runpy.run_path', return_value={'stage': stage, 'digest': lambda path: hashlib.sha256(path.read_bytes()).hexdigest()}), \
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
                self.assertEqual(volumes[1]['persistentVolumeClaim']['claimName'], 'jenkins-home-migrated')
                receipts = list(root.glob('.local-work/private/phase9/*/restore-receipt.json'))
                self.assertEqual(len(receipts), 1)
                self.assertTrue(json.loads(receipts[0].read_text())['runtime_acceptance_pending'])

    def test_restores_only_new_pvc_and_retains_read_only_foundation(self):
        self.invoke()

    def test_existing_migration_pvc_is_never_overwritten(self):
        self.invoke(existing=True)

    def test_hash_mismatch_prevents_target_start(self):
        self.invoke(bad_hash=True)


if __name__ == '__main__':
    unittest.main()
