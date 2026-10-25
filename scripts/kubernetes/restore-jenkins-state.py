#!/usr/bin/env python3
"""Back up or restore a held Jenkins home; preserve the original PVC and administrator."""

import argparse
import datetime
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile

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


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


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
    pod = json.loads(run(['get', 'pod', helper, '-o', 'json']))
    target = next(v['persistentVolumeClaim']['claimName'] for v in desired['spec']['template']['spec']['volumes'] if v['name'] == 'home')
    if next(v['persistentVolumeClaim']['claimName'] for v in pod['spec']['volumes'] if v['name'] == 'restore') != target:
        raise RuntimeError('Transfer helper target does not match the recorded PVC')
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


def backup_home(directory):
    """Copy a stopped current home through a read-only helper; leave Jenkins stopped."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    runpy.run_path(str(ROOT / 'scripts/kubernetes/deploy-jenkins-agents.py'))['held_request']()
    deployment = json.loads(run(['get', 'deployment', 'jenkins', '-o', 'json']))
    spec = deployment['spec']['template']['spec']
    home = next(v for v in spec['volumes'] if v['name'] == 'home')
    pods = json.loads(run(['get', 'pods', '-l', 'app.kubernetes.io/name=jenkins', '-o', 'json']))['items']
    if len(pods) != 1 or deployment['spec']['replicas'] != 1:
        raise RuntimeError('Expected one controller; inspect before backup')
    save(directory / 'deployment-before.json', json.dumps(deployment).encode())
    for volume in spec['volumes']:
        if 'configMap' in volume:
            name = volume['configMap']['name']
            save(directory / ('configmap-' + name + '.json'), run(['get', 'configmap', name, '-o', 'json']))
    helper = 'jenkins-home-backup-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
    pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': helper, 'namespace': 'jenkins'},
           'spec': {'restartPolicy': 'Never', 'nodeSelector': {'kubernetes.io/hostname': pods[0]['spec']['nodeName']},
                    'automountServiceAccountToken': False, 'imagePullSecrets': spec.get('imagePullSecrets', []),
                    'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'fsGroup': 1000},
                    'containers': [{'name': 'backup', 'image': spec['containers'][0]['image'],
                                    'command': ['sleep', '86400'],
                                    'resources': {'requests': {'cpu': '10m', 'memory': '64Mi'}, 'limits': {'cpu': '1', 'memory': '256Mi'}},
                                    'volumeMounts': [{'name': 'home', 'mountPath': '/home-copy', 'readOnly': True}]}],
                    'volumes': [dict(home, persistentVolumeClaim={**home['persistentVolumeClaim'], 'readOnly': True})]}}
    run(['scale', 'deployment/jenkins', '--replicas=0'])
    run(['wait', '--for=delete', 'pod', '-l', 'app.kubernetes.io/name=jenkins', '--timeout=180s'])
    apply(pod)
    run(['wait', '--for=condition=Ready', 'pod/' + helper, '--timeout=300s'])
    target = directory / 'home.tar.gz'
    with target.open('xb') as stream:
        result = subprocess.run(KUBE + ['exec', helper, '--', 'tar', '-czf', '-', '-C', '/home-copy', '.'],
                                stdout=stream, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Backup interrupted; keep controller stopped and inspect helper')
    files = expected_files(target)
    if not {'config.xml', 'secrets/master.key', 'secrets/hudson.util.Secret'} <= files.keys():
        raise RuntimeError('Incomplete controller archive')
    save(directory / 'manifest.json', json.dumps({'mode': 'stopped-preservation', 'consistent': True,
         'helper': helper, 'archives': [{'file': 'home.tar.gz', 'bytes': target.stat().st_size,
         'sha256': file_digest(target)}]}).encode())
    print(json.dumps({'backup_directory': str(directory), 'helper': helper, 'controller_stopped': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-only', type=Path, help='New private output directory; leaves controller stopped')
    parser.add_argument('backup_directory', type=Path, nargs='?')
    parser.add_argument('--target-pvc', default='jenkins-home-restored',
                        help='New empty PVC name; existing PVCs are never overwritten')
    parser.add_argument('--resume-verified-copy', type=Path,
                        help='Verify an already-copied new PVC before completing an interrupted transfer')
    args = parser.parse_args()
    os.umask(0o077)
    if args.backup_only:
        backup_home(args.backup_only)
        return
    stage_module = runpy.run_path(str(ROOT / 'scripts/kubernetes/stage-jenkins-home.py'))
    if args.resume_verified_copy:
        directory = args.resume_verified_copy
        context = json.loads((directory / 'transfer-context.json').read_text())
        current = json.loads(run(['get', 'deployment', 'jenkins', '-o', 'json']))
        current_home = next(v['persistentVolumeClaim']['claimName'] for v in current['spec']['template']['spec']['volumes'] if v['name'] == 'home')
        if current_home != context.get('source_pvc', 'jenkins-home'):
            raise RuntimeError('Resume source home differs from the recorded deployment')
        if current['spec']['replicas'] != 0:
            raise RuntimeError('Resume requires the controller to remain stopped')
        backup = json.loads((directory / 'foundation-backup.json').read_text())
        if stage_module['digest'](directory / 'foundation-home.tar.gz') != backup['sha256']:
            raise RuntimeError('Foundation rollback archive integrity mismatch')
        finish_transfer(directory, context)
        return
    if args.backup_directory is None:
        parser.error('backup_directory is required for a new transfer')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', args.target_pvc):
        raise RuntimeError('Invalid target PVC name')
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / '.local-work/private/phase9' / ('restore-' + timestamp)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if run(['get', 'pvc', args.target_pvc, '--ignore-not-found', '-o', 'name']).strip():
        raise RuntimeError('Migration PVC already exists; inspect before any retry')
    runpy.run_path(str(ROOT / 'scripts/kubernetes/deploy-jenkins-agents.py'))['held_request']()
    deployment = json.loads(run(['get', 'deployment', 'jenkins', '-o', 'json']))
    spec = deployment['spec']['template']['spec']
    volumes = {entry['name']: entry for entry in spec['volumes']}
    if deployment['spec']['replicas'] != 1:
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
    save(directory / 'foundation-configmap.json', run(['get', 'configmap', volumes['config']['configMap']['name'], '-o', 'json']))
    expected_lock = (ROOT / 'kubernetes/platform/upstream/infra/jenkins-host/plugins.lock.txt').read_bytes()
    if run(['exec', source_pod, '--', 'cat', '/usr/share/jenkins/ref/plugins.txt']) != expected_lock:
        raise RuntimeError('Controller plugin lock differs from the preserved source')
    source_manifest = json.loads((args.backup_directory / 'manifest.json').read_text())
    if source_manifest.get('mode') != 'stopped-preservation' or source_manifest.get('consistent') is not True:
        raise RuntimeError('Restore requires a consistent stopped-controller backup')
    saved_deployment = args.backup_directory / 'deployment-before.json'
    if saved_deployment.is_file():
        saved_image = json.loads(saved_deployment.read_text())['spec']['template']['spec']['containers'][0]['image']
        if saved_image != spec['containers'][0]['image']:
            raise RuntimeError('Source and target controller image pins differ')
    staged = directory / 'staged'
    stage_module['stage'](args.backup_directory, staged)
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
    # Keep the existing controller image/resources and restore only to new storage.
    desired['spec']['template']['spec']['containers'] = copy.deepcopy(spec['containers'])
    for container in desired['spec']['template']['spec']['containers']:
        container['volumeMounts'] = [m for m in container.get('volumeMounts', []) if m.get('subPath') != 'agent-hold.groovy']
    new_volumes['home']['persistentVolumeClaim']['claimName'] = args.target_pvc
    held_resources = list(yaml.safe_load_all((manifests / 'held/migration-hold.yaml').read_text()))
    for resource in held_resources:
        if resource['kind'] == 'PersistentVolumeClaim':
            resource['metadata']['name'] = args.target_pvc
            source_claim = json.loads(run(['get', 'pvc', volumes['home']['persistentVolumeClaim']['claimName'], '-o', 'json']))
            resource['spec'] = {key: value for key, value in source_claim['spec'].items()
                                if key in {'accessModes', 'storageClassName', 'resources', 'volumeMode'}}
        run(['apply', '--dry-run=server', '-f', '-'], json.dumps(resource).encode())
    run(['apply', '--dry-run=server', '-f', '-'], json.dumps(desired).encode())
    for resource in held_resources:
        if resource['kind'] == 'PersistentVolumeClaim':
            run(['create', '-f', '-'], json.dumps(resource).encode())
        else:
            apply(resource)
    run(['scale', 'deployment/jenkins', '--replicas=0'])
    run(['wait', '--for=delete', 'pod', '-l', 'app.kubernetes.io/name=jenkins', '--timeout=180s'])
    print(json.dumps({'step': 'foundation-stopped', 'rollback': str(directory / 'rollback-deployment.json')}), flush=True)
    helper = 'jenkins-state-transfer-' + timestamp.lower()
    context = {'helper': helper, 'deployment': desired, 'backup_source': str(args.backup_directory),
               'source_pvc': volumes['home']['persistentVolumeClaim']['claimName']}
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
                 'volumes': [{'name': 'foundation', 'persistentVolumeClaim': {'claimName': volumes['home']['persistentVolumeClaim']['claimName'], 'readOnly': True}},
                             {'name': 'restore', 'persistentVolumeClaim': {'claimName': args.target_pvc}}]}}
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
