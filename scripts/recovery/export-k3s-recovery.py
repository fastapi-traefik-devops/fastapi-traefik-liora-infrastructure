#!/usr/bin/env python3
"""Copy an existing etcd snapshot, original server token and node identities.

Reads servers over verified SSH. Does not create a snapshot or change a server.
Every output is private; raw SSH errors and secret values are never printed.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CLUSTERS = {
    'nonprod': [('k3s-1-0' + str(i), '192.168.77.' + str(200 + i)) for i in range(1, 4)],
    'prod': [('k3s-2-0' + str(i), '192.168.77.' + str(210 + i)) for i in range(1, 4)],
}


def remote(ssh, code):
    command = 'sudo -n python3 -c ' + shlex.quote(code)
    result = subprocess.run(ssh + [command], capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError('SSH read failed; inspect access and source files privately')
    return result.stdout


def write_private(path, value):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    for directory in missing:
        directory.chmod(0o700)
    with path.open('xb') as stream:
        stream.write(value)
    path.chmod(0o600)
    return hashlib.sha256(value).hexdigest()


def export(args):
    identities_only = getattr(args, 'identities_only', False)
    token_dir = getattr(args, 'token_dir', ROOT / 'recovery')
    if not identities_only and args.output.resolve().is_relative_to((ROOT / 'recovery').resolve()):
        raise ValueError('Snapshot files must be outside recovery/; use --identities-only for the private kit')
    if args.output.exists():
        raise ValueError('Choose a new output directory; preserve earlier recovery sets')
    args.output.mkdir(parents=True, mode=0o700)
    args.output.chmod(0o700)
    manifest = {'version': 1, 'cluster': args.cluster, 'complete': False,
                'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'nodes': []}
    token = None
    for index, (name, address) in enumerate(CLUSTERS[args.cluster]):
        ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o',
               'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(args.known_hosts),
               '-i', str(args.identity), 'root-admin@' + address]
        current = remote(ssh, "from pathlib import Path; import sys; sys.stdout.buffer.write(Path('/var/lib/rancher/k3s/server/token').read_bytes())")
        if not current.strip() or len(current) > 4096:
            raise ValueError('Missing or invalid source server token')
        if token is None:
            token = current
            token_path = token_dir / ('k3s-' + args.cluster + '-server.token') if identities_only else args.output / 'server.token'
            if token_path.exists():
                if token_path.is_symlink() or token_path.read_bytes() != current:
                    raise ValueError('Fixed token differs; preserve the previous token before replacing it')
                token_path.chmod(0o600)
                manifest['token_sha256'] = hashlib.sha256(current).hexdigest()
            else:
                manifest['token_sha256'] = write_private(token_path, current)
        elif current.strip() != token.strip():
            raise ValueError('Server tokens differ; preserve the partial set and investigate')
        password = remote(ssh, "from pathlib import Path; import sys; sys.stdout.buffer.write(Path('/etc/rancher/node/password').read_bytes())")
        if not password.strip() or len(password) > 4096:
            raise ValueError('Missing or invalid node identity')
        digest = write_private(args.output / 'nodes' / name / 'password', password)
        manifest['nodes'].append({'name': name, 'address': address, 'password_sha256': digest})
        if index == 0 and identities_only:
            meta = json.loads(remote(ssh, """
import json, subprocess
print(json.dumps({'k3s_version': subprocess.check_output(['/usr/local/bin/k3s','--version'], text=True).splitlines()[0],
 'cluster_uid': subprocess.check_output(['/usr/local/bin/k3s','kubectl','--request-timeout=20s','get','namespace','kube-system','-o','jsonpath={.metadata.uid}'], text=True)}))
"""))
            manifest.update(identities_only=True, k3s_version=meta['k3s_version'], cluster_uid=meta['cluster_uid'])
        if index == 0 and not identities_only:
            meta = json.loads(remote(ssh, """
from pathlib import Path
import json, hashlib, subprocess
files = [p for p in Path('/var/lib/rancher/k3s/server/db/snapshots').glob('etcd-snapshot-*') if p.is_file() and not p.is_symlink()]
if not files: raise SystemExit(1)
p = max(files, key=lambda p: p.stat().st_mtime)
print(json.dumps({'snapshot': str(p), 'snapshot_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
 'k3s_version': subprocess.check_output(['/usr/local/bin/k3s','--version'], text=True).splitlines()[0],
 'cluster_uid': subprocess.check_output(['/usr/local/bin/k3s','kubectl','--request-timeout=20s','get','namespace','kube-system','-o','jsonpath={.metadata.uid}'], text=True)}))
"""))
            path = Path(meta['snapshot'])
            if path.parent != Path('/var/lib/rancher/k3s/server/db/snapshots') or not path.name.startswith('etcd-snapshot-'):
                raise ValueError('Unexpected snapshot path')
            blob = remote(ssh, 'from pathlib import Path; import sys; sys.stdout.buffer.write(Path(' + repr(str(path)) + ').read_bytes())')
            digest = write_private(args.output / path.name, blob)
            if digest != meta['snapshot_sha256']:
                raise ValueError('Snapshot changed or copy is incomplete; do not use this recovery set')
            manifest.update(snapshot=path.name, snapshot_sha256=digest, k3s_version=meta['k3s_version'], cluster_uid=meta['cluster_uid'])
    manifest['complete'] = True
    write_private(args.output / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())
    print(json.dumps({'cluster': args.cluster, 'complete': True, 'directory': str(args.output),
                      'snapshot': manifest.get('snapshot'), 'nodes': len(manifest['nodes'])}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=CLUSTERS, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    parser.add_argument('--identity', type=Path, default=ROOT / 'recovery/LIORA-id_ed25519')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--identities-only', action='store_true', help='Save the fixed server token and node identities, without copying snapshots')
    args = parser.parse_args()
    try:
        export(args)
    except Exception as error:
        print('Recovery export stopped (' + type(error).__name__ + '); preserve partial files and inspect privately', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
