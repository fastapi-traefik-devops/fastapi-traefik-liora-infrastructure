#!/usr/bin/env python3
"""Check the approved stop boundary with fake Docker/Jenkins endpoints."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'stop-legacy-ci.py'
SECRET = 'FIXTURE-ONLY-STOP-PRIVATE-c936'


class Response(io.BytesIO):
    def __init__(self, value):
        super().__init__(json.dumps(value).encode())


class StopTests(unittest.TestCase):
    def invoke(self, forced=False):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[2] / '.local-work') as directory:
            root = Path(directory)
            script = root / 'scripts/kubernetes/stop-legacy-ci.py'
            script.parent.mkdir(parents=True)
            script.write_text(SCRIPT.read_text())
            module = runpy.run_path(str(script))
            namespace = module['main'].__globals__
            names = namespace['CONTAINERS']
            events = []
            inspected = 0
            queue = [{'id': 12}]

            def docker(*arguments):
                nonlocal inspected
                events.append(arguments)
                if arguments[0] == 'inspect':
                    inspected += 1
                    return json.dumps([{'Name': '/' + name, 'Image': 'fixture-image',
                        'State': {'Running': inspected == 1, 'ExitCode': 137 if forced else 0},
                        'Mounts': []} for name in names]).encode()
                if arguments[:2] == ('exec', 'host-jenkins'):
                    return SECRET.encode()
                return b''

            def endpoint(req, **kwargs):
                events.append((req.get_method(), req.full_url.split('8085')[-1]))
                path = req.full_url.split('8085')[-1]
                if path == '/crumbIssuer/api/json':
                    return Response({'crumbRequestField': 'crumb', 'crumb': SECRET})
                if path.startswith('/queue/cancelItem'):
                    queue.clear()
                if path.startswith('/queue/'):
                    return Response({'items': list(queue)})
                if path.startswith('/computer/'):
                    return Response({'computer': [{'executors': [{'currentExecutable': {'url': 'in-flight'}}]}]})
                return Response({'quietingDown': True})

            def capture(container, source, path, command=None):
                self.assertIsNotNone(command)
                self.assertIn('type=volume,source=host-jenkins-home,target=/source,readonly', command)
                self.assertIn('none', command)
                self.assertNotIn('--rm', command)
                with tarfile.open(path, 'w:gz') as archive:
                    for name in ['config.xml', 'secrets/master.key', 'secrets/hudson.util.Secret']:
                        entry = tarfile.TarInfo(name)
                        entry.size = len(SECRET)
                        archive.addfile(entry, io.BytesIO(SECRET.encode()))
                return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': 'fixture'}

            opener = type('Opener', (), {'open': staticmethod(endpoint)})()
            stdout = io.StringIO()
            with patch.dict(namespace, docker=docker, capture=capture), \
                    patch('urllib.request.build_opener', return_value=opener), \
                    patch.object(sys, 'argv', [str(script), '--stop-active']), redirect_stdout(stdout):
                if forced:
                    with self.assertRaises(RuntimeError):
                        module['main']()
                else:
                    module['main']()
            self.assertNotIn(SECRET, stdout.getvalue())
            self.assertEqual([event[3] for event in events if event[:1] == ('stop',)], names)
            self.assertFalse(any(event[0] in {'rm', 'volume', 'prune'} for event in events))
            manifests = list(root.glob('.local-work/private/phase9/*/manifest.json'))
            if forced:
                self.assertFalse(manifests)
            else:
                result = json.loads(manifests[0].read_text())
                self.assertTrue(result['consistent'])
                self.assertFalse(result['restore_tested'])
                self.assertEqual(result['inflight_executors_at_stop'], 1)
                boundary = json.loads((manifests[0].parent / 'stop-boundary.json').read_text())
                self.assertFalse(boundary['drained'])

    def test_immediate_stop_records_inflight_and_preserves_containers(self):
        self.invoke()

    def test_forced_controller_stop_cannot_claim_clean_backup(self):
        self.invoke(forced=True)


if __name__ == '__main__':
    unittest.main()
