#!/usr/bin/env python3
"""Create one cluster's Slack Secret using hidden prompts, without writing credentials to disk."""
import argparse
import base64
import getpass
import json
import subprocess
import sys
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=['nonprod', 'prod'], required=True)
    parser.add_argument('--kubeconfig', required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('Run from an interactive terminal so webhook prompts cannot echo credentials.')
    kubectl = ['kubectl', '--kubeconfig', args.kubeconfig, '-n', 'monitoring']
    # Inspect a non-secret cluster identity before collecting any credentials.
    prometheus = json.loads(subprocess.check_output(kubectl + ['get', 'prometheus', 'monitoring-prometheus', '-o', 'json']))
    if prometheus['spec'].get('externalLabels', {}).get('cluster') != args.cluster:
        raise SystemExit('Cluster identity mismatch; check --cluster and --kubeconfig.')
    name = 'monitoring-slack-' + args.cluster
    existing = subprocess.run(kubectl + ['get', 'secret', name, '--ignore-not-found', '-o', 'name'],
                              capture_output=True, text=True, check=True)
    if existing.stdout.strip():
        raise SystemExit('Secret already exists; review rotation separately rather than overwriting it.')
    data = {}
    for key, channel in [('normal-webhook', 'liora-alerts-' + args.cluster),
                         ('testing-webhook', 'liora-alerts-testing')]:
        value = getpass.getpass(f'Webhook authorized for #{channel} ({args.cluster}): ').strip()
        parsed = urlparse(value)
        if (parsed.scheme != 'https' or parsed.netloc != 'hooks.slack.com'
                or not parsed.path.startswith('/services/') or parsed.query or parsed.fragment):
            raise SystemExit('Expected an HTTPS Slack incoming webhook URL; value was not logged.')
        if value in data.values():
            raise SystemExit('Normal and testing destinations must use different webhooks.')
        data[key] = value
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
              'metadata': {'name': name, 'namespace': 'monitoring'},
              'data': {key: base64.b64encode(value.encode()).decode() for key, value in data.items()}}
    result = subprocess.run(kubectl + ['create', '-f', '-'], input=json.dumps(secret),
                            text=True, capture_output=True)
    if result.returncode:
        # Kubernetes errors can echo request data; never print them for this operation.
        raise SystemExit('Secret creation failed. Inspect Kubernetes access and existing Secret metadata; credentials were not logged.')
    print(f'Created {name} in {args.cluster}; webhook channel bindings still require verification in Slack.')


if __name__ == '__main__':
    main()
