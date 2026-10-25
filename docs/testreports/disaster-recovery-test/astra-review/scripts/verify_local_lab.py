#!/usr/bin/env python3
"""Read-only checks for the retained 2026-10-24 lab. Never starts/stops resources."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess

NODE = 'k3d-liora-dr-20261024-server-0'
UID = 'aa85f393-9b41-42a5-af6a-7fadfc783683'
ORIGINALS = ('infra-agent-1', 'infra-jenkins-1', 'infra-docker-1')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(args):
    # Print no credential-bearing inspect fields or raw subprocess diagnostics.
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, f'Command failed (exit {result.returncode}): {args[0]}')
    return result.stdout.strip()


def deployment_ready(obj):
    desired = obj.get('spec', {}).get('replicas', 1)
    status = obj.get('status', {})
    require(desired > 0, 'Zero replicas cannot prove deployment readiness')
    require(status.get('observedGeneration', 0) >= obj['metadata']['generation'],
            'Controller has not observed current generation')
    require(status.get('updatedReplicas', 0) == desired and
            status.get('availableReplicas', 0) == desired and
            status.get('replicas', 0) == desired, 'Deployment not fully available')


def verify(mode, run=command):
    if mode == 'stopped':
        for name in (NODE, *ORIGINALS):
            state = run(['docker', 'inspect', '--format', '{{.State.Status}}', name])
            require(state in ('exited', 'created'), f'Expected stopped container: {name}')
        for name in ORIGINALS:
            count = run(['docker', 'inspect', '--format', '{{len .Mounts}}', name])
            require(int(count) > 0, f'Expected retained mounts: {name}')
        require(not run(['docker', 'ps', '-q']), 'Running containers remain; nothing was stopped by this verifier')
        require(run(['kubectl', 'config', 'current-context']) == 'k3d-gitlab-gitops',
                'Original default context changed')
        return {'mode': mode, 'status': 'PASS', 'original_mount_attachments_present': True,
                'all_containers_stopped': True, 'scope': 'Read-only local stop/mount/context recheck, not a fresh recovery run'}
    require(mode == 'running', 'Unsupported mode')
    def k(*args):
        return run(['docker', 'exec', NODE, 'kubectl', *args])
    require(k('get', 'namespace', 'kube-system', '-o', 'jsonpath={.metadata.uid}') == UID,
            'Wrong lab UID; refusing remaining queries')
    for ns, name in [('cnpg-system', 'cnpg-controller-manager'),
                     ('cnpg-system', 'barman-cloud'), ('cert-manager', 'cert-manager'),
                     ('cert-manager', 'cert-manager-webhook'), ('cert-manager', 'cert-manager-cainjector')]:
        deployment_ready(json.loads(k('-n', ns, 'get', 'deployment', name, '-o', 'json')))
    pvc = json.loads(k('-n', 'dr-storage', 'get', 'pvc', '-o', 'json'))
    require(bool(pvc['items']) and all(p['status']['phase'] == 'Bound' for p in pvc['items']),
            'Storage PVC absent or not Bound')
    deployment_ready(json.loads(k('-n', 'dr-storage', 'get', 'deployment', 'persistence', '-o', 'json')))
    require(k('-n', 'dr-storage', 'exec', 'deployment/persistence', '--', 'cat', '/data/marker') ==
            'liora-dr-20261024', 'Persistent marker mismatch')
    return {'mode': mode, 'status': 'PASS', 'cluster_uid': UID,
            'scope': 'Current lab dependency/storage verification only; not R2 or application recovery'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['stopped', 'running'], required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory outside this Git repository')
    args = parser.parse_args()
    out = args.output.resolve()
    repo = Path(__file__).resolve().parents[5]
    require(not out.is_relative_to(repo), 'Write results outside the published repository')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)  # Refuse existing evidence before any command.
    result = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    code = 0
    try:
        result.update(verify(args.mode))
    except Exception as exc:
        code = 1
        result.update(status='FAIL', error=str(exc), mode=args.mode)
    result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out / 'verification.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
