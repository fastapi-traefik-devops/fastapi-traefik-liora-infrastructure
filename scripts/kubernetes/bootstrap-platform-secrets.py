#!/usr/bin/env python3
"""Provision Phase 8 logins without printing credentials or rotating live Secrets."""

import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', required=True, choices=['nonprod', 'prod'])
    parser.add_argument('--component', required=True, choices=['monitoring', 'jenkins'])
    args = parser.parse_args()
    if args.component == 'jenkins' and args.cluster != 'nonprod':
        parser.error('Jenkins belongs only to nonprod')
    root = Path(__file__).resolve().parents[2]
    kubeconfig = Path.home() / '.kube' / ('config-dev-stage' if args.cluster == 'nonprod' else 'config-prod')
    command = ['kubectl', '--kubeconfig=' + str(kubeconfig)]
    namespace = args.component
    private = root / '.local-work/private/platform'
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    credentials = private / (args.cluster + '-' + args.component + '.json')
    name = 'monitoring-grafana-admin' if namespace == 'monitoring' else 'jenkins-foundation-login'

    def run(arguments, data=None):
        result = subprocess.run(command + arguments, input=data, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError('Kubernetes operation failed; diagnostics suppressed')
        return result.stdout

    # Look up namespace and Secret without dumping objects or values.
    run(['apply', '-f', '-'], json.dumps({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace}}))
    existing = run(['-n', namespace, 'get', 'secret', name, '--ignore-not-found', '-o', 'name']).strip()
    if existing:
        print('Existing login Secret preserved; no credentials were rotated.')
        return 0
    if credentials.exists():
        if credentials.stat().st_mode & 0o077:
            raise ValueError('Private input permissions must be 0600')
        entry = json.loads(credentials.read_text())
    else:
        entry = {'username': 'admin007@liora.aprt.info' if namespace == 'monitoring' else 'admin',
                 'password': secrets.token_urlsafe(32)}
        with os.fdopen(os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(entry, stream)
            stream.write('\n')
    if not entry.get('username') or len(entry.get('password', '')) < 32:
        raise ValueError('Invalid private login input')
    data = ({'admin-user': entry['username'], 'admin-password': entry['password']}
            if namespace == 'monitoring' else {'jenkins-admin-password': entry['password']})
    objects = [{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': namespace},
                'type': 'Opaque', 'stringData': data}]
    if namespace == 'jenkins':
        # Reuse the existing recovery registry identity, without shell evaluation.
        registry = {}
        for line in (root / 'recovery/.env').read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            key, raw = line.removeprefix('export ').split('=', 1)
            values = shlex.split(raw, comments=True)
            if values:
                registry[key.strip()] = values[0]
        if registry['GHCR_REGISTRY'] != 'ghcr.io':
            raise ValueError('Unexpected registry')
        auth = base64.b64encode((registry['GHCR_USERNAME'] + ':' + registry['GHCR_TOKEN']).encode()).decode()
        config = {'auths': {'ghcr.io': {'auth': auth}}}
        pull_exists = run(['-n', namespace, 'get', 'secret', 'ghcr-pull-secret', '--ignore-not-found', '-o', 'name']).strip()
        if not pull_exists:
            objects.append({'apiVersion': 'v1', 'kind': 'Secret',
                            'metadata': {'name': 'ghcr-pull-secret', 'namespace': namespace},
                            'type': 'kubernetes.io/dockerconfigjson',
                            'stringData': {'.dockerconfigjson': json.dumps(config)}})
    # Create only: an existing Secret appearing concurrently must never be overwritten.
    run(['create', '-f', '-'], json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects}))
    print('Platform Secrets created; private recovery input: ' + str(credentials))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('Platform bootstrap failed: ' + type(error).__name__ + '; credential diagnostics suppressed', file=sys.stderr)
        sys.exit(1)
