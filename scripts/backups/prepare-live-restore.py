#!/usr/bin/env python3
"""Catalog R2 backups or prepare a fresh-environment live recovery bundle.

No database or application is applied. --provision-r2 creates only a missing,
matching R2 Secret after refusing an existing target Cluster or PVC. All other
operations are local writes and read-only Kubernetes/S3 requests.
"""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

import boto3
from botocore.config import Config
import yaml

class RecoveryError(ValueError):
    pass


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = 'barman-cloud.cloudnative-pg.io'


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('Operator command failed; inspect target/access privately')
    return result.stdout


def render(environment):
    raw = command(['kubectl', 'kustomize', str(ROOT / 'kubernetes/apps/liora/overlays' / environment)])
    return list(yaml.safe_load_all(raw))


def select(objects, kind, name):
    return next(copy.deepcopy(o) for o in objects if o['kind'] == kind and o['metadata']['name'] == name)


def destination(value, environment):
    uri = urlparse(value)
    if (uri.scheme != 's3' or uri.netloc != 'liora-backup' or uri.query or uri.fragment
            or not uri.path.startswith('/' + environment + '/') or '..' in uri.path
            or '//' in uri.path or not uri.path.endswith('/')):
        raise RecoveryError('Use the environment prefix in the dedicated R2 bucket')
    return uri.netloc, uri.path.lstrip('/')


def utc(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise RecoveryError('An explicit recovery-target timezone is required')
    return parsed.astimezone(dt.timezone.utc)


def location(objects, environment, source_destination=None, source_server=None):
    cluster = select(objects, 'Cluster', 'liora-db')
    plugin = next(p for p in cluster['spec']['plugins'] if p['name'] == PLUGIN and p.get('isWALArchiver'))
    store = select(objects, 'ObjectStore', plugin['parameters']['barmanObjectName'])
    path = source_destination or store['spec']['configuration']['destinationPath']
    server = source_server or plugin['parameters']['serverName']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,61}[a-z0-9]', server):
        raise RecoveryError('Invalid archive server identity')
    destination(path, environment)
    store['spec']['configuration']['destinationPath'] = path
    return cluster, store, server


def client(directory):
    value = yaml.safe_load((directory / 'recovery.yaml').read_text())['database_backups']
    if value['bucket'] != 'liora-backup':
        raise RecoveryError('Unexpected backup bucket')
    return boto3.client('s3', endpoint_url=value['endpoint'], region_name=value['region'],
                        aws_access_key_id=value['access_key_id'], aws_secret_access_key=value['secret_access_key'],
                        config=Config(connect_timeout=10, read_timeout=20, retries={'max_attempts': 0})), value


def backup_catalog(s3, bucket, prefix, server):
    base = prefix + server + '/base/'
    names = set()
    token = None
    deadline = time.monotonic() + 120
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError('Catalog enumeration deadline')
        page = s3.list_objects_v2(Bucket=bucket, Prefix=base, **({'ContinuationToken': token} if token else {}))
        for obj in page.get('Contents', []):
            suffix = obj['Key'].removeprefix(base)
            if re.fullmatch(r'\d{8}T\d{6}/backup.info', suffix):
                names.add(obj['Key'])
        if not page.get('IsTruncated'):
            break
        following = page.get('NextContinuationToken')
        if not following or following == token:
            raise RecoveryError('Invalid catalog pagination')
        token = following
    records = []
    for name in sorted(names):
        if time.monotonic() > deadline:
            raise TimeoutError('Catalog metadata deadline')
        body = s3.get_object(Bucket=bucket, Key=name)['Body']
        try:
            raw = body.read(1024 * 1024)
        finally:
            body.close()
        fields = dict(line.split('=', 1) for line in raw.decode().splitlines() if '=' in line)
        record = {key: fields[key].strip().strip('\"\'') for key in
                  ['backup_id', 'status', 'begin_time', 'end_time', 'version', 'begin_wal', 'end_wal'] if key in fields}
        record['backup_id'] = name.split('/')[-2]
        records.append(record)
    return records


def check_empty_target(kubeconfig, environment):
    base = ['kubectl', '--kubeconfig', str(kubeconfig), '--request-timeout=20s', '-n', 'app-' + environment]
    cluster = command(base + ['get', 'clusters.postgresql.cnpg.io', 'liora-db', '--ignore-not-found', '-o', 'json'])
    claims = json.loads(command(base + ['get', 'pvc', '-o', 'json']))
    workloads = json.loads(command(base + ['get', 'deployments', '-o', 'json']))
    jobs = json.loads(command(base + ['get', 'jobs', '-o', 'json']))
    if cluster.strip() or claims['items']:
        raise RecoveryError('Existing target Cluster/PVC: preserve it; no in-place restore')
    if any(o['spec'].get('replicas', 1) > 0 for o in workloads['items']):
        raise RecoveryError('Application workloads must be held at zero replicas')
    if any(o.get('status', {}).get('active', 0) for o in jobs['items']):
        raise RecoveryError('Active initialization/other Jobs must finish or be held')
    return base


def provision_r2(base, values):
    import base64
    expected = {key: base64.b64encode(values[field].encode()).decode() for key, field in
                [('ACCESS_KEY_ID', 'access_key_id'), ('SECRET_ACCESS_KEY', 'secret_access_key'),
                 ('ENDPOINT_URL', 'endpoint'), ('REGION', 'region')]}
    raw = command(base + ['get', 'secret', 'r2-backup', '--ignore-not-found', '-o', 'json'])
    if raw.strip():
        if json.loads(raw).get('data') != expected:
            raise RecoveryError('Existing R2 credentials differ; no automatic rotation')
        return
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'r2-backup'},
              'type': 'Opaque', 'data': expected}
    command(base + ['create', '-f', '-'], json.dumps(secret).encode())


def build(objects, environment, backup_id, target_time, source_destination, source_server, recovery_id):
    if not re.fullmatch(r'\d{8}T\d{6}', backup_id):
        raise RecoveryError('Use a physical Barman backup ID, not a Kubernetes Backup name')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,22}[a-z0-9])?', recovery_id):
        raise RecoveryError('Recovery ID must be a short lowercase DNS label')
    target = utc(target_time)
    if target > dt.datetime.now(dt.timezone.utc):
        raise RecoveryError('Recovery target is in the future')
    cluster, store, server = location(objects, environment, source_destination, source_server)
    ns = 'app-' + environment
    source = copy.deepcopy(store)
    source['metadata'] = {'name': 'restore-source', 'namespace': ns,
                          'annotations': {'argocd.argoproj.io/sync-options': 'Prune=false,Delete=false',
                                          'argocd.argoproj.io/sync-wave': '-3'}}
    source['spec'].pop('retentionPolicy', None)
    archive = 'liora-' + environment + '-r-' + recovery_id
    target_path = 's3://liora-backup/' + environment + '/recovery-' + recovery_id + '/'
    store['metadata']['namespace'] = ns
    store['spec']['configuration']['destinationPath'] = target_path
    bootstrap = {'recovery': {'source': 'restore-source', 'recoveryTarget':
                 {'backupID': backup_id, 'targetTime': target.isoformat().replace('+00:00', 'Z')}}}
    external = [{'name': 'restore-source', 'plugin': {'name': PLUGIN,
                'parameters': {'barmanObjectName': 'restore-source', 'serverName': server}}}]
    plugins = [{'name': PLUGIN, 'isWALArchiver': True,
                'parameters': {'barmanObjectName': store['metadata']['name'], 'serverName': archive}}]
    cluster['spec'].update(bootstrap=bootstrap, externalClusters=external, plugins=plugins)
    cluster['metadata']['namespace'] = ns
    # Stable endpoint, original resources/placement and original application images remain unchanged.
    config = [copy.deepcopy(o) for o in objects if o['kind'] not in ['Cluster', 'ObjectStore', 'Job']]
    maintenance = copy.deepcopy(config)
    for obj in maintenance:
        if obj['kind'] == 'Deployment':
            obj['spec']['replicas'] = 0
    jobs = [copy.deepcopy(o) for o in objects if o['kind'] == 'Job']
    cluster_patch = [{'op': 'replace', 'path': '/spec/bootstrap', 'value': bootstrap},
                     {'op': 'add', 'path': '/spec/externalClusters', 'value': external},
                     {'op': 'replace', 'path': '/spec/plugins', 'value': plugins}]
    store_patch = [{'op': 'replace', 'path': '/spec/configuration/destinationPath', 'value': target_path}]
    fragment = {'resources': ['recovery/source-archive.yaml'], 'patches': [
        {'target': {'group': 'postgresql.cnpg.io', 'kind': 'Cluster', 'name': 'liora-db'},
         'path': 'recovery/cluster-patch.yaml'},
        {'target': {'group': 'barmancloud.cnpg.io', 'kind': 'ObjectStore', 'name': 'r2-backup'},
         'path': 'recovery/objectstore-patch.yaml'}]}
    return {'database.yaml': [source, store, cluster], 'maintenance.yaml': maintenance,
            'application.yaml': config, 'prestart.yaml': jobs,
            'gitops-patches/kustomization-fragment.yaml': [fragment],
            'gitops-patches/cluster-patch.yaml': cluster_patch,
            'gitops-patches/objectstore-patch.yaml': store_patch,
            'gitops-patches/source-archive.yaml': [source]}, target_path, archive



def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['catalog', 'prepare'])
    p.add_argument('--environment', required=True, choices=['dev', 'stage', 'prod'])
    p.add_argument('--source-destination')
    p.add_argument('--source-server')
    p.add_argument('--recovery-dir', type=Path, default=ROOT / 'recovery')
    p.add_argument('--backup-id')
    p.add_argument('--target-time')
    p.add_argument('--recovery-id')
    p.add_argument('--output', type=Path)
    p.add_argument('--kubeconfig', type=Path)
    p.add_argument('--provision-r2', action='store_true')
    args = p.parse_args()
    try:
        objects = render(args.environment)
        _, store, server = location(objects, args.environment, args.source_destination, args.source_server)
        bucket, prefix = destination(store['spec']['configuration']['destinationPath'], args.environment)
        if args.action == 'prepare':
            if not all([args.backup_id, args.target_time, args.recovery_id, args.output]) or args.output.exists():
                raise RecoveryError('Prepare needs selection inputs and a new output directory')
            kubeconfig = args.kubeconfig or Path.home() / '.kube' / ('config-prod' if args.environment == 'prod' else 'config-dev-stage')
            base = check_empty_target(kubeconfig, args.environment)
        s3, values = client(args.recovery_dir)
        records = backup_catalog(s3, bucket, prefix, server)
        if args.action == 'catalog':
            print(json.dumps({'environment': args.environment, 'destination': store['spec']['configuration']['destinationPath'],
                              'server': server, 'backups': records}, indent=2))
            return 0
        record = next(r for r in records if r['backup_id'] == args.backup_id)
        if record.get('status') != 'DONE' or utc(record['end_time']) > utc(args.target_time):
            raise RecoveryError('Select a completed backup ending before the recovery target')
        files, target_path, archive = build(objects, args.environment, args.backup_id, args.target_time,
            args.source_destination, args.source_server, args.recovery_id)
        _, new_prefix = destination(target_path, args.environment)
        if s3.list_objects_v2(Bucket=bucket, Prefix=new_prefix, MaxKeys=1).get('KeyCount', 0):
            raise RecoveryError('Post-recovery destination is not empty; preserve it and choose a new identity')
        if args.provision_r2:
            provision_r2(base, values)
        args.output.mkdir(parents=True, mode=0o700)
        for name, resources in files.items():
            path = args.output / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_text(yaml.safe_dump(resources, sort_keys=False) if name.endswith('-patch.yaml')
                            else yaml.safe_dump_all(resources, sort_keys=False))
            path.chmod(0o600)
        print(json.dumps({'prepared': True, 'environment': args.environment, 'source_backup': args.backup_id,
                          'new_destination': target_path, 'new_server': archive, 'directory': str(args.output)}))
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, RecoveryError) else type(error).__name__ + '; inspect privately'
        print('Live recovery preparation stopped: ' + reason + '; no database applied', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
