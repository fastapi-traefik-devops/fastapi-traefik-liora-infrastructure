#!/usr/bin/env python3
"""One-time, allowlisted cleanup authorized on 2026-10-25; default is inspection.

Preserve fixed tokens and canonical identities first. Never contacts nodes/R2.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    ('nonprod', 'etcd/nonprod-20261025', 'etcd-snapshot-k3s-1-01-1792929602'),
    ('prod', 'etcd/prod-20261025', 'etcd-snapshot-k3s-2-01-1792929601'),
    ('nonprod', 'etcd-r2-downloads/nonprod-20261025', 'etcd-snapshot-k3s-1-01-1792939090.zip'),
    ('nonprod', 'etcd-r2-downloads/nonprod-recovery-set-20261025', 'etcd-snapshot-k3s-1-01-1792939090.zip'),
    ('prod', 'etcd-r2-downloads/prod-recovery-set-20261025', 'etcd-snapshot-k3s-2-01-1792939379.zip'),
]


def run(execute):
    files = []; directories = []; evidence = []
    for cluster in ['nonprod', 'prod']:
        subprocess.run([sys.executable, str(ROOT/'scripts/recovery/verify-k3s-recovery.py'),
                        str(ROOT/'recovery/k3s-identities'/f'{cluster}-20261025')], check=True, capture_output=True)
    for cluster, relative, snapshot in TARGETS:
        root = ROOT/'recovery'/relative
        if root.is_symlink(): raise ValueError('Indirect cleanup root')
        if not root.exists(): continue
        token = ROOT/'recovery'/f'k3s-{cluster}-server.token'
        canonical = ROOT/'recovery/k3s-identities'/f'{cluster}-20261025'
        manifest = json.loads((canonical/'manifest.json').read_text())
        expected = {'manifest.json', 'server.token', snapshot}
        expected.update('nodes/'+n['name']+'/password' for n in manifest['nodes'])
        for path in root.rglob('*'):
            if path.is_symlink(): raise ValueError('Symlink in cleanup target')
            if path.is_dir(): directories.append(path); continue
            name = path.relative_to(root).as_posix()
            if not path.is_file() or name not in expected: raise ValueError('Unrecognized artifact; preserve it')
            if name == 'server.token' and path.read_bytes() != token.read_bytes(): raise ValueError('Token differs; do not delete')
            if name.startswith('nodes/') and path.read_bytes() != (canonical/name).read_bytes(): raise ValueError('Node identity differs; do not delete')
            if name == 'manifest.json':
                original = json.loads(path.read_text())
                if original['cluster_uid'] != manifest['cluster_uid'] or original['token_sha256'] != manifest['token_sha256']:
                    raise ValueError('Metadata differs; do not delete')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            evidence.append({'file': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': digest})
            files.append(path)
        directories.append(root)
    if execute and files:
        target = ROOT/'.local-work/etcd-r2/cleanup-evidence.json'
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open('x') as stream: json.dump(evidence, stream, indent=2)
        target.chmod(0o600)
        for path in files: path.unlink()
        for path in sorted(set(directories), key=lambda p: len(p.parts), reverse=True): path.rmdir()
        for path in [ROOT/'recovery/etcd', ROOT/'recovery/etcd-r2-downloads']:
            if path.exists() and not any(path.iterdir()): path.rmdir()
    print(json.dumps({'executed': execute, 'files': len(files), 'bytes': sum(x['bytes'] for x in evidence),
                      'fixed_tokens_and_canonical_identities_preserved': True}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--execute', action='store_true')
    try: run(p.parse_args().execute)
    except Exception as error: raise SystemExit('Cleanup stopped ('+type(error).__name__+'); preserve remaining inputs')
