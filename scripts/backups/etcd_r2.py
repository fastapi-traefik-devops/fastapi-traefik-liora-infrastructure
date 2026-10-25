#!/usr/bin/env python3
"""List or download/verify native etcd snapshots. Never restore or delete snapshots."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

import boto3
from botocore.config import Config
import yaml

ROOT = Path(__file__).resolve().parents[2]


def snapshot_name(cluster, name):
    group = '1' if cluster == 'nonprod' else '2'
    return re.fullmatch(r'etcd-snapshot-k3s-' + group + r'-0[123]-[0-9]+\.zip', name) is not None


def list_snapshots(client, bucket, cluster):
    prefix = 'etcd/' + cluster + '/'
    result = []; token = None; deadline = time.monotonic() + 120
    while True:
        if time.monotonic() > deadline: raise TimeoutError('R2 list deadline')
        page = client.list_objects_v2(Bucket=bucket, Prefix=prefix, **({'ContinuationToken': token} if token else {}))
        result.extend(o for o in page.get('Contents', []) if snapshot_name(cluster, o['Key'].removeprefix(prefix)) and o['Size'] > 0)
        if not page.get('IsTruncated'): return sorted(result, key=lambda o: o['LastModified'], reverse=True)
        following = page.get('NextContinuationToken')
        if not following or following == token: raise ValueError('Invalid pagination')
        token = following


def verify_snapshot(path):
    # Native compressed snapshots contain one etcd snapshot with an appended SHA-256.
    # Streaming reads also check ZIP CRC. No etcd process is started.
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != path.name.removesuffix('.zip'):
            raise ValueError('Unexpected snapshot archive contents')
        digest = hashlib.sha256(); tail = b''; size = 0
        with archive.open(members[0]) as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk); chunk = tail + chunk
                digest.update(chunk[:-32]); tail = chunk[-32:]
        if size <= 32 or digest.digest() != tail: raise ValueError('Etcd snapshot checksum mismatch')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def attach_identity(source, output, snapshot, digest, metadata, cluster):
    checked = subprocess.run([sys.executable, str(ROOT / 'scripts/recovery/verify-k3s-recovery.py'), str(source)], capture_output=True, timeout=90)
    if checked.returncode: raise ValueError('Original recovery identity set failed verification')
    manifest = json.loads((source / 'manifest.json').read_text())
    token = (source / 'server.token').read_text().strip()
    password = token.split('::', 1)[1].split(':', 1)[1] if token.startswith('K10') else token
    token_hash = hashlib.sha256(password.encode()).hexdigest()[:12]
    if (manifest['cluster'] != cluster or metadata.get('k3s-cluster-id') != manifest['cluster_uid']
            or metadata.get('k3s-token-hash') != token_hash):
        raise ValueError('Snapshot metadata does not match the selected token/cluster')
    shutil.copyfile(source / 'server.token', output / 'server.token')
    (output / 'server.token').chmod(0o600)
    for node in manifest['nodes']:
        target = output / 'nodes' / node['name']
        target.mkdir(parents=True, mode=0o700)
        (output / 'nodes').chmod(0o700)
        shutil.copyfile(source / 'nodes' / node['name'] / 'password', target / 'password')
        (target / 'password').chmod(0o600)
    manifest.update(snapshot=snapshot, snapshot_sha256=digest,
                    captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    source_r2_key='etcd/' + cluster + '/' + snapshot)
    path = output / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n');path.chmod(0o600)


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['list', 'download'])
    p.add_argument('--cluster', choices=['nonprod', 'prod'], required=True)
    p.add_argument('--recovery-dir', type=Path, default=ROOT / 'recovery')
    p.add_argument('--snapshot')
    p.add_argument('--output', type=Path)
    p.add_argument('--identity-set', type=Path, help='Matching complete token/node recovery set; build a runbook-21 recovery set')
    args = p.parse_args()
    try:
        value = yaml.safe_load((args.recovery_dir / 'recovery.yaml').read_text())['database_backups']
        if value['bucket'] != 'liora-backup': raise ValueError('Unexpected bucket')
        client = boto3.client('s3', endpoint_url=value['endpoint'], region_name=value['region'],
            aws_access_key_id=value['access_key_id'], aws_secret_access_key=value['secret_access_key'],
            config=Config(connect_timeout=10, read_timeout=20, retries={'max_attempts': 0}))
        objects = list_snapshots(client, value['bucket'], args.cluster)
        if args.action == 'list':
            print(json.dumps([{'name': Path(o['Key']).name, 'key': o['Key'], 'bytes': o['Size'], 'uploaded_at': o['LastModified'].isoformat()} for o in objects], indent=2)); return
        if not args.snapshot or not snapshot_name(args.cluster, args.snapshot) or args.output is None:
            raise ValueError('Download needs an exact snapshot name and new output directory')
        key = 'etcd/' + args.cluster + '/' + args.snapshot
        if key not in [o['Key'] for o in objects]: raise ValueError('Selected snapshot is absent')
        args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        path = args.output / args.snapshot
        response = client.get_object(Bucket=value['bucket'], Key=key)
        body = response['Body']
        try:
            with path.open('xb') as stream:
                while chunk := body.read(1024 * 1024): stream.write(chunk)
        finally: body.close()
        sha = verify_snapshot(path)
        if args.identity_set:
            attach_identity(args.identity_set, args.output, args.snapshot, sha, response.get('Metadata', {}), args.cluster)
        print(json.dumps({'key': key, 'download': str(path), 'sha256': sha, 'zip_crc_and_etcd_sha256': True, 'restoration_performed': False}))
    except Exception as error:
        raise SystemExit('Etcd R2 operation stopped (' + type(error).__name__ + '); preserve files and inspect privately')


if __name__ == '__main__': main()
