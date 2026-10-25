#!/usr/bin/env python3
"""Check a complete local recovery set without printing tokens or passwords."""
import hashlib
import json
from pathlib import Path
import sys


def verify(directory):
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError('Recovery directory must be private and not a symlink')
    manifest_path = directory / 'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_mode & 0o077:
        raise ValueError('Manifest must be private and not a symlink')
    manifest = json.loads(manifest_path.read_text())
    if (not manifest.get('complete') or manifest.get('version') != 1
            or manifest.get('cluster') not in ['nonprod', 'prod']
            or not manifest.get('cluster_uid') or not manifest.get('k3s_version')
            or len(manifest.get('nodes', [])) != 3):
        raise ValueError('Incomplete recovery set')
    snapshot = manifest['snapshot']
    if Path(snapshot).name != snapshot or not snapshot.startswith('etcd-snapshot-'):
        raise ValueError('Invalid snapshot filename')
    expected_names = {'k3s-' + ('2' if manifest['cluster'] == 'prod' else '1') + '-0' + str(i) for i in range(1, 4)}
    if {n['name'] for n in manifest['nodes']} != expected_names:
        raise ValueError('Unexpected node identities')
    files = [('server.token', manifest['token_sha256']), (snapshot, manifest['snapshot_sha256'])]
    files.extend(('nodes/' + n['name'] + '/password', n['password_sha256']) for n in manifest['nodes'])
    for name, digest in files:
        path = directory / name
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError('Recovery file must be private and not a symlink')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Recovery file checksum mismatch')
    return {'complete': True, 'cluster': manifest['cluster'], 'snapshot': snapshot,
            'k3s_version': manifest['k3s_version'], 'nodes': len(manifest['nodes'])}


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Usage: verify-k3s-recovery.py RECOVERY_SET_DIRECTORY')
        print(json.dumps(verify(Path(sys.argv[1]))))
    except Exception as error:
        raise SystemExit('Recovery-set check stopped (' + type(error).__name__ + '); inspect files privately')
