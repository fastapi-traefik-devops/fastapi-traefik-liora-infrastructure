"""Offline tests; no node or Kubernetes mutations."""
import argparse
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

h = load('hold', 'hold-restored-workloads.py')
e = load('exporter', 'export-k3s-recovery.py')
v = load('verifier', 'verify-k3s-recovery.py')


class HoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.args = argparse.Namespace(manifest=root / 'manifest.json', state=root / 'hold.json', resume=False)
        self.args.manifest.write_text(json.dumps({'complete': True, 'cluster_uid': 'cluster-one'}))
        self.calls = []

    def api(self, args, body=None):
        self.calls.append((args, body))
        if args[:2] == ['get', 'namespace']: return {'metadata': {'uid': 'cluster-one'}}
        if args[0] != 'get': return {}
        kind = args[1]
        metadata = {'name': 'fixture', 'namespace': 'fixture-ns', 'uid': 'original-uid'}
        if kind == 'applications.argoproj.io': return {'items': [{'metadata': metadata, 'spec': {'syncPolicy': {'automated': {'prune': True}}}}]}
        if kind in ['deployments.apps', 'statefulsets.apps']: return {'items': [{'metadata': metadata, 'spec': {'replicas': 2}}]}
        if kind in ['jobs.batch', 'cronjobs.batch']: return {'items': [{'metadata': metadata, 'spec': {}}]}
        if kind == 'pods':
            return {'items': [{'metadata': dict(metadata), 'status': {'phase': 'Running'}},
                              {'metadata': {**metadata, 'name': 'daemon', 'ownerReferences': [{'kind': 'DaemonSet'}]}}]}
        self.fail('Unexpected API read')

    def test_original_intent_saved_uid_guards_and_resume(self):
        def guarded(args, body=None):
            if 'patch' in args or args[0] == 'delete': self.assertTrue(self.args.state.exists())
            return self.api(args, body)
        with patch.object(h, 'kube', side_effect=guarded), contextlib.redirect_stdout(io.StringIO()): h.hold(self.args)
        state = json.loads(self.args.state.read_text())
        self.assertTrue(state['complete'])
        self.assertEqual([i['replicas'] for i in state['resources'] if 'replicas' in i], [2, 2])
        mutations = [c for c in self.calls if 'patch' in c[0]]
        self.assertEqual(mutations[0][0][3], 'applications.argoproj.io')
        for args, _ in mutations: self.assertEqual(json.loads(args[-1])[0]['op'], 'test')
        deletes = [c for c in self.calls if c[0][0] == 'delete']
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0][1]['preconditions']['uid'], 'original-uid')
        self.assertNotIn('daemon', deletes[0][0][2])
        for args, _ in self.calls:
            self.assertFalse(any(v in args for v in ['pvc', 'pv', 'secrets', 'namespaces']))
        with patch.object(h, 'kube', side_effect=guarded):
            with self.assertRaises(ValueError): h.hold(self.args)
        self.args.resume = True
        with patch.object(h, 'kube', side_effect=guarded), contextlib.redirect_stdout(io.StringIO()): h.hold(self.args)
        self.assertEqual(json.loads(self.args.state.read_text())['resources'], state['resources'])

    def test_wrong_cluster_stops_before_writes(self):
        with patch.object(h, 'kube', return_value={'metadata': {'uid': 'other'}}) as api:
            with self.assertRaises(ValueError): h.hold(self.args)
        self.assertEqual(api.call_count, 1)
        self.assertFalse(self.args.state.exists())


class ExportTest(unittest.TestCase):
    def test_complete_set_private_and_secret_free_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(output=Path(tmp) / 'set', cluster='nonprod', known_hosts=Path('hosts'), identity=Path('key'))
            blob = b'snapshot-canary'; secret = b'FIXTURE_SECRET_CANARY'
            def remote(ssh, code):
                if 'server/token' in code or 'node/password' in code: return secret
                if 'files =' in code:
                    return json.dumps({'snapshot': '/var/lib/rancher/k3s/server/db/snapshots/etcd-snapshot-fixture', 'snapshot_sha256': hashlib.sha256(blob).hexdigest(), 'k3s_version': 'fixture', 'cluster_uid': 'fixture-uid'}).encode()
                return blob
            stream = io.StringIO()
            with patch.object(e, 'remote', side_effect=remote), contextlib.redirect_stdout(stream): e.export(args)
            self.assertNotIn(secret.decode(), stream.getvalue())
            state = json.loads((args.output / 'manifest.json').read_text())
            self.assertTrue(state['complete']); self.assertEqual(len(state['nodes']), 3)
            self.assertEqual(v.verify(args.output)['cluster'], 'nonprod')
            for path in args.output.rglob('*'):
                self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
            with self.assertRaises(ValueError): e.export(args)
            (args.output / 'server.token').write_bytes(b'altered')
            with self.assertRaises(ValueError): v.verify(args.output)

    def test_identity_capture_saves_fixed_token_without_snapshot_or_token_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=argparse.Namespace(output=root/'identities',cluster='nonprod',known_hosts=Path('hosts'),identity=Path('key'),identities_only=True,token_dir=root/'private')
            def remote(ssh,code):
                if 'server/token' in code:return b'FIXTURE_TOKEN'
                if 'node/password' in code:return b'FIXTURE_NODE_PASSWORD'
                self.assertNotIn('glob(',code)
                return json.dumps({'k3s_version':'fixture','cluster_uid':'fixture-uid'}).encode()
            with patch.object(e,'remote',side_effect=remote),contextlib.redirect_stdout(io.StringIO()):e.export(args)
            token=args.token_dir/'k3s-nonprod-server.token'
            self.assertEqual(token.read_bytes(),b'FIXTURE_TOKEN')
            self.assertFalse((args.output/'server.token').exists())
            self.assertFalse(list(args.output.glob('etcd-snapshot-*')))
            self.assertTrue(v.verify(args.output,token)['identities_only'])

    def test_fixed_token_is_not_overwritten_on_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);token=root/'k3s-prod-server.token';token.write_bytes(b'old-token');token.chmod(0o600)
            args=argparse.Namespace(output=root/'identities',cluster='prod',known_hosts=Path('hosts'),identity=Path('key'),identities_only=True,token_dir=root)
            with patch.object(e,'remote',return_value=b'new-token'):
                with self.assertRaises(ValueError):e.export(args)
            self.assertEqual(token.read_bytes(),b'old-token')
            self.assertFalse((args.output/'manifest.json').exists())

    def test_token_mismatch_keeps_partial_set_without_complete_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(output=Path(tmp) / 'set', cluster='prod', known_hosts=Path('hosts'), identity=Path('key'))
            digest = hashlib.sha256(b'snapshot').hexdigest()
            meta = json.dumps({'snapshot': '/var/lib/rancher/k3s/server/db/snapshots/etcd-snapshot-fixture', 'snapshot_sha256': digest, 'k3s_version': 'fixture', 'cluster_uid': 'fixture'}).encode()
            with patch.object(e, 'remote', side_effect=[b'one', b'password', meta, b'snapshot', b'different']):
                with self.assertRaises(ValueError): e.export(args)
            with self.assertRaises(FileNotFoundError): v.verify(args.output)
            self.assertTrue((args.output / 'server.token').exists())
            self.assertFalse((args.output / 'manifest.json').exists())


if __name__ == '__main__': unittest.main()
