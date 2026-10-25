#!/usr/bin/env python3
"""Hold recovered API objects before enabling any restored node's K3s agent.

Run only on the first agentless restore server, after stopping all old runtimes.
Keeps original replicas/policies in a private, resumable state file. Does not
change PVCs, PVs, Secrets, namespaces, Services or DaemonSets.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

KUBE = ['/usr/local/bin/k3s', 'kubectl', '--kubeconfig=/etc/rancher/k3s/k3s.yaml', '--request-timeout=20s']


def kube(args, body=None):
    result = subprocess.run(KUBE + args, input=json.dumps(body).encode() if body is not None else None,
                            capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Restored API operation failed; preserve the state file')
    return json.loads(result.stdout) if result.stdout.strip() else None


def save(path, state):
    tmp = path.with_suffix('.partial')
    with tmp.open('w') as stream:
        json.dump(state, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.chmod(0o600)
    tmp.replace(path)


def identity(obj):
    return {key: obj['metadata'][key] for key in ['name', 'namespace', 'uid']}


def patch(kind, item, changes):
    # Reject resource replacement between capture and mutation.
    operations = [{'op': 'test', 'path': '/metadata/uid', 'value': item['uid']}] + changes
    kube(['-n', item['namespace'], 'patch', kind, item['name'], '--type=json', '-p', json.dumps(operations)])


def hold(args):
    manifest = json.loads(args.manifest.read_text())
    if not manifest.get('complete') or not manifest.get('cluster_uid'):
        raise ValueError('A complete recovery-set manifest is required')
    uid = kube(['get', 'namespace', 'kube-system', '-o', 'json'])['metadata']['uid']
    if uid != manifest['cluster_uid']:
        raise ValueError('Recovered cluster identity does not match the snapshot recovery set')
    if args.state.exists():
        if not args.resume:
            raise ValueError('Use explicit --resume with the original state file')
        state = json.loads(args.state.read_text())
        if state['cluster_uid'] != uid:
            raise ValueError('State file belongs to another cluster')
    else:
        if args.resume:
            raise ValueError('Original state file is missing')
        state = {'version': 1, 'cluster_uid': uid, 'complete': False, 'resources': [], 'pod_deletions': []}
        for kind in ['applications.argoproj.io', 'deployments.apps', 'statefulsets.apps', 'cronjobs.batch', 'jobs.batch']:
            for obj in kube(['get', kind, '-A', '-o', 'json'])['items']:
                item = {**identity(obj), 'kind': kind}
                if kind == 'applications.argoproj.io':
                    item['syncPolicy'] = obj['spec'].get('syncPolicy', {})
                elif kind in ['deployments.apps', 'statefulsets.apps']:
                    item['replicas'] = obj['spec'].get('replicas', 1)
                else:
                    item['suspend'] = obj['spec'].get('suspend', False)
                state['resources'].append(item)
        args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        save(args.state, state)  # Preserve original intent before any mutations.
    apps = [i for i in state['resources'] if i['kind'] == 'applications.argoproj.io']
    for item in sorted(apps, key=lambda i: not i['name'].startswith('liora-root-')):
        policy = {**item['syncPolicy'], 'automated': {'enabled': False}}
        patch(item['kind'], item, [{'op': 'add', 'path': '/spec/syncPolicy', 'value': policy}])
    for item in state['resources']:
        kind = item['kind']
        if kind == 'applications.argoproj.io':
            continue
        key, value = ('replicas', 0) if kind in ['deployments.apps', 'statefulsets.apps'] else ('suspend', True)
        patch(kind, item, [{'op': 'add', 'path': '/spec/' + key, 'value': value}])
    # Old bound Pod objects must not start database/application processes when agents return.
    for obj in kube(['get', 'pods', '-A', '-o', 'json'])['items']:
        meta = obj['metadata']
        if (obj.get('status', {}).get('phase') in ['Succeeded', 'Failed'] or meta.get('deletionTimestamp')
                or 'kubernetes.io/config.mirror' in meta.get('annotations', {})
                or any(o['kind'] == 'DaemonSet' for o in meta.get('ownerReferences', []))):
            continue
        item = identity(obj)
        state['pod_deletions'].append(item)
        save(args.state, state)
        body = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': item['uid']},
                'propagationPolicy': 'Background'}
        kube(['delete', '--raw', '/api/v1/namespaces/' + item['namespace'] + '/pods/' + item['name'], '-f', '-'], body)
    state['complete'] = True
    save(args.state, state)
    print(json.dumps({'held': True, 'state': str(args.state), 'resources': len(state['resources'])}))


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--confirm-all-agents-stopped', action='store_true')
    args = p.parse_args()
    try:
        config = Path('/etc/rancher/k3s/config.yaml').read_text()
        if (os.geteuid() != 0 or not args.confirm_all_agents_stopped
                or not re.search(r'^disable-agent:\s*true\s*$', config, re.M)):
            raise ValueError('Require root, agentless configuration and explicit runtime-stop confirmation')
        for path in Path('/proc').glob('[0-9]*/comm'):
            try:
                if 'containerd-shim' in path.read_text():
                    raise ValueError('A container runtime still has workload processes')
            except (FileNotFoundError, PermissionError):
                pass
        hold(args)
        return 0
    except Exception as error:
        print('Restored workload hold stopped (' + type(error).__name__ + '); retain agentless mode and inspect privately', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
