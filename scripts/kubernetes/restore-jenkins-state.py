#!/usr/bin/env python3
"""Restore held Jenkins state to a NEW NONPROD PVC; retain the foundation home."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[2]
KUBE = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'), '-n', 'jenkins']


def run(arguments, data=None):
    result = subprocess.run(KUBE + arguments, input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError('Kubernetes operation failed; private diagnostics suppressed')
    return result.stdout


def save(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(data)


def apply(value):
    return run(['apply', '-f', '-'], json.dumps(value).encode())


def expected_files(path):
    result = {}
    with tarfile.open(path) as archive:
        for member in archive:
            if member.isfile():
                digest = hashlib.sha256()
                stream = archive.extractfile(member)
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
                result[member.name.removeprefix('./')] = digest.hexdigest()
    return result


def finish_transfer(directory, context):
    helper, desired = context['helper'], context['deployment']
    expected = json.loads((directory / 'expected-files.json').read_text())
    hashes = run(['exec', helper, '--', 'find', '/restore', '-type', 'f', '-exec', 'sha256sum', '{}', '+'])
    actual = {}
    for line in hashes.decode().splitlines():
        digest, name = line.split(None, 1)
        actual[name.removeprefix('/restore/')] = digest
    if actual != expected:
        raise RuntimeError('Restored file hashes differ; controller remains stopped')
    save(directory / 'transfer-verified.json', json.dumps({'files_verified': len(expected),
         'admin_login_preserved': True, 'original_pvc_retained': True, 'helper': helper}).encode())
    run(['exec', helper, '--', 'touch', '/restore/.transfer-complete'])
    run(['wait', '--for=jsonpath={.status.phase}=Succeeded', 'pod/' + helper, '--timeout=60s'])
    apply(desired)
    print(json.dumps({'step': 'held-controller-starting'}), flush=True)
    run(['rollout', 'status', 'deployment/jenkins', '--timeout=900s'])
    save(directory / 'restore-receipt.json', json.dumps({'backup_source': context['backup_source'],
         'files_verified': len(expected), 'original_pvc_retained': True,
         'runtime_acceptance_pending': True, 'rollback_deployment': str(directory / 'rollback-deployment.json')}).encode())
    print(json.dumps({'step': 'restored-ready', 'directory': str(directory), 'runtime_acceptance_pending': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup_directory', type=Path, nargs='?')
    parser.add_argument('--resume-verified-copy', type=Path,
                        help='Verify an already-copied new PVC before completing an interrupted transfer')
    args = parser.parse_args()
    stage_module = runpy.run_path(str(ROOT / 'scripts/kubernetes/stage-jenkins-home.py'))
    if args.resume_verified_copy:
        directory = args.resume_verified_copy
        context = json.loads((directory / 'transfer-context.json').read_text())
        current = json.loads(run(['get', 'deployment', 'jenkins', '-o', 'json']))
        if current['spec']['replicas'] != 0:
            raise RuntimeError('Resume requires the controller to remain stopped')
        backup = json.loads((directory / 'foundation-backup.json').read_text())
        if stage_module['digest'](directory / 'foundation-home.tar.gz') != backup['sha256']:
            raise RuntimeError('Foundation rollback archive integrity mismatch')
        finish_transfer(directory, context)
        return
    if args.backup_directory is None:
        parser.error('backup_directory is required for a new transfer')
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / '.local-work/private/phase9' / ('restore-' + timestamp)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if run(['get', 'pvc', 'jenkins-home-migrated', '--ignore-not-found', '-o', 'name']).strip():
        raise RuntimeError('Migration PVC already exists; inspect before any retry')
    deployment = json.loads(run(['get', 'deployment', 'jenkins', '-o', 'json']))
    spec = deployment['spec']['template']['spec']
    volumes = {entry['name']: entry for entry in spec['volumes']}
    if volumes['home']['persistentVolumeClaim']['claimName'] != 'jenkins-home' or deployment['spec']['replicas'] != 1:
        raise RuntimeError('Expected the running foundation with its original home')
    pods = json.loads(run(['get', 'pods', '-l', 'app.kubernetes.io/name=jenkins', '-o', 'json']))['items']
    if len(pods) != 1 or pods[0]['status']['phase'] != 'Running':
        raise RuntimeError('Expected exactly one running foundation Pod')
    source_pod = pods[0]['metadata']['name']
    node = pods[0]['spec']['nodeName']
    save(directory / 'deployment-before.json', json.dumps(deployment).encode())
    # Save an apply-ready rollback object without server-owned metadata/status.
    rollback = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
                'metadata': {'name': 'jenkins', 'namespace': 'jenkins'}, 'spec': deployment['spec']}
    save(directory / 'rollback-deployment.json', json.dumps(rollback).encode())
    save(directory / 'foundation-configmap.json', run(['get', 'configmap', 'jenkins-foundation', '-o', 'json']))
    admin_data = run(['exec', source_pod, '--', 'sh', '-c', 'cat /var/jenkins_home/users/*/config.xml'])
    if ET.fromstring(admin_data).findtext('id') != 'admin':
        raise RuntimeError('Expected the sole current foundation admin user')
    admin = directory / 'current-admin.xml'
    save(admin, admin_data)
    expected_lock = (ROOT / 'kubernetes/platform/upstream/infra/jenkins-host/plugins.lock.txt').read_bytes()
    if run(['exec', source_pod, '--', 'cat', '/usr/share/jenkins/ref/plugins.txt']) != expected_lock:
        raise RuntimeError('Controller plugin lock differs from the preserved source')
    staged = directory / 'staged'
    stage_module['stage'](args.backup_directory, staged, admin)
    expected = expected_files(staged / 'inactive-home.tar.gz')
    save(directory / 'expected-files.json', json.dumps(expected).encode())
    print(json.dumps({'step': 'inactive-copy-prepared', 'directory': str(directory)}), flush=True)

    manifests = ROOT / 'kubernetes/platform/nonprod/jenkins'
    desired = next(item for item in yaml.safe_load_all(run(['kustomize', str(manifests / 'held')]).decode())
                   if item['kind'] == 'Deployment')
    new_volumes = {entry['name']: entry for entry in desired['spec']['template']['spec']['volumes']}
    if (new_volumes['home']['persistentVolumeClaim']['claimName'] != 'jenkins-home-migrated' or
            new_volumes['config']['configMap']['name'] != 'jenkins-migration-hold'):
        raise RuntimeError('Expected the reviewed held migration manifest')
    run(['apply', '--dry-run=server', '-f', str(manifests / 'held/migration-hold.yaml')])
    run(['apply', '--dry-run=server', '-f', '-'], json.dumps(desired).encode())
    run(['apply', '-f', str(manifests / 'held/migration-hold.yaml')])
    run(['scale', 'deployment/jenkins', '--replicas=0'])
    run(['wait', '--for=delete', 'pod', '-l', 'app.kubernetes.io/name=jenkins', '--timeout=180s'])
    print(json.dumps({'step': 'foundation-stopped', 'rollback': str(directory / 'rollback-deployment.json')}), flush=True)
    helper = 'jenkins-state-transfer-' + timestamp.lower()
    context = {'helper': helper, 'deployment': desired, 'backup_source': str(args.backup_directory)}
    save(directory / 'transfer-context.json', json.dumps(context).encode())
    helper_spec = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': helper, 'namespace': 'jenkins'},
        'spec': {'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                 'nodeSelector': {'kubernetes.io/hostname': node},
                 'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000},
                 'imagePullSecrets': spec.get('imagePullSecrets', []),
                 'containers': [{'name': 'transfer', 'image': spec['containers'][0]['image'],
                    'command': ['sh', '-c', 'while [ ! -e /restore/.transfer-complete ]; do sleep 2; done'],
                    'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'},
                                  'limits': {'cpu': '1', 'memory': '256Mi'}},
                    'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                    'volumeMounts': [{'name': 'foundation', 'mountPath': '/foundation', 'readOnly': True},
                                     {'name': 'restore', 'mountPath': '/restore'}]}],
                 'volumes': [{'name': 'foundation', 'persistentVolumeClaim': {'claimName': 'jenkins-home', 'readOnly': True}},
                             {'name': 'restore', 'persistentVolumeClaim': {'claimName': 'jenkins-home-migrated'}}]}}
    apply(helper_spec)
    run(['wait', '--for=condition=Ready', 'pod/' + helper, '--timeout=300s'])
    backup = directory / 'foundation-home.tar.gz'
    with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        result = subprocess.run(KUBE + ['exec', helper, '--', 'tar', '-czf', '-', '-C', '/foundation', '.'],
                                stdout=stream, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Foundation backup failed; original PVC retained')
    with tarfile.open(backup) as archive:
        names = {entry.name.removeprefix('./') for entry in archive}
    if not {'config.xml', 'secrets/master.key'} <= names:
        raise RuntimeError('Foundation backup lacks required material')
    save(directory / 'foundation-backup.json', json.dumps({'consistent': True, 'restore_tested': False,
         'sha256': stage_module['digest'](backup), 'bytes': backup.stat().st_size}).encode())
    print(json.dumps({'step': 'foundation-backed-up'}), flush=True)
    with (staged / 'inactive-home.tar.gz').open('rb') as stream:
        result = subprocess.run(KUBE + ['exec', '-i', helper, '--', 'sh', '-c',
                                'test -z "$(ls -A /restore)" && tar --exclude=. -xzof - -C /restore'],
                                stdin=stream, capture_output=True)
    if result.returncode:
        raise RuntimeError('New-PVC restore failed; inspect private state before retry')
    finish_transfer(directory, context)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'restore_complete': False, 'error_type': type(error).__name__,
                          'action': 'Inspect the private receipt; no automatic cleanup or rollback was performed.'}), file=sys.stderr)
        sys.exit(1)
