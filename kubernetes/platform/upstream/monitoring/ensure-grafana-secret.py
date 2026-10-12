#!/usr/bin/env python3
"""Create the monitoring admin Secret if absent; never print or persist credentials."""
import json
import secrets
import subprocess

kubectl = ['kubectl', '--context', 'kind-fastapi-dev', '-n', 'monitoring']
name = 'monitoring-grafana-admin'
result = subprocess.run(kubectl + ['get', 'secret', name, '--ignore-not-found', '-o', 'json'],
                        check=True, capture_output=True, text=True)
if result.stdout.strip():
    data = json.loads(result.stdout).get('data', {})
    if not all(data.get(key) for key in ('admin-user', 'admin-password')):
        raise SystemExit('Existing Grafana Secret lacks required keys; left unchanged.')
    print('Existing Grafana admin Secret preserved.')
else:
    secret = {'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
              'metadata': {'name': name, 'namespace': 'monitoring'},
              'stringData': {'admin-user': 'admin', 'admin-password': secrets.token_urlsafe(32)}}
    # stdin avoids exposing the password through process arguments or files.
    result = subprocess.run(kubectl + ['create', '-f', '-'], input=json.dumps(secret),
                            capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('Grafana Secret creation failed; no credential output retained.')
    print('Grafana admin Secret created; credentials stored only in Kubernetes.')
