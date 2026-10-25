#!/usr/bin/env python3
"""Check a complete local recovery set without printing tokens or passwords."""
import hashlib
import json
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[2]


def verify(directory, token_file=None):
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
    identities_only = manifest.get('identities_only') is True
    snapshot = manifest.get('snapshot')
    if not identities_only and (not isinstance(snapshot, str) or Path(snapshot).name != snapshot or not snapshot.startswith('etcd-snapshot-')):
        raise ValueError('Invalid snapshot filename')
    expected_names = {'k3s-' + ('2' if manifest['cluster'] == 'prod' else '1') + '-0' + str(i) for i in range(1, 4)}
    if {n['name'] for n in manifest['nodes']} != expected_names:
        raise ValueError('Unexpected node identities')
    token_path = token_file or (ROOT / 'recovery' / ('k3s-' + manifest['cluster'] + '-server.token') if identities_only else directory / 'server.token')
    files = [(token_path, manifest['token_sha256'])]
    if not identities_only:
        files.append((directory / snapshot, manifest['snapshot_sha256']))
    files.extend((directory / 'nodes' / n['name'] / 'password', n['password_sha256']) for n in manifest['nodes'])
    for path, digest in files:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError('Recovery file must be private and not a symlink')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Recovery file checksum mismatch')
    return {'complete': True, 'cluster': manifest['cluster'], 'snapshot': snapshot,
            'k3s_version': manifest['k3s_version'], 'nodes': len(manifest['nodes']), 'identities_only': identities_only}


if __name__ == '__main__':
    try:
        p = argparse.ArgumentParser(description=__doc__)
        p.add_argument('directory', type=Path)
        p.add_argument('--token-file', type=Path)
        args = p.parse_args()
        print(json.dumps(verify(args.directory, args.token_file)))
    except Exception as error:
        raise SystemExit('Recovery-set check stopped (' + type(error).__name__ + '); inspect files privately')
