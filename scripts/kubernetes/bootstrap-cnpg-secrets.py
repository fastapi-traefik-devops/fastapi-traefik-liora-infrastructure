#!/usr/bin/env python3
"""Provision CNPG bootstrap credentials from existing application Secrets.

Never rotate passwords or overwrite a mismatching existing CNPG Secret.
The application owner is app_owner; postgres remains an administrative login.
"""
import argparse
import base64
import json
import subprocess
import sys


def provision(kubeconfig, environment):
    base = ['kubectl', '--kubeconfig', kubeconfig, '-n', 'app-' + environment]

    def get(name):
        result = subprocess.run(base + ['get', 'secret', name, '--ignore-not-found', '-o', 'json'],
                                capture_output=True, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    backend, database = get('backend-secrets'), get('db-secrets')
    assert backend and database, 'Existing application Secrets are required'
    password = backend['data']['POSTGRES_PASSWORD']
    assert base64.b64decode(password) and password == database['data']['POSTGRES_PASSWORD'], 'Database passwords must agree'
    for name, username in [('cnpg-app', 'app_owner'), ('cnpg-superuser', 'postgres')]:
        data = {'username': base64.b64encode(username.encode()).decode(), 'password': password}
        existing = get(name)
        if existing:
            assert existing['type'] == 'kubernetes.io/basic-auth' and existing['data'] == data, 'Existing CNPG Secret differs; review privately'
            continue
        obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': 'app-' + environment},
               'type': 'kubernetes.io/basic-auth', 'data': data}
        subprocess.run(base + ['create', '-f', '-'], input=json.dumps(obj).encode(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print('CNPG bootstrap Secrets ready; existing passwords unchanged')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--environment', required=True, choices=['dev', 'stage', 'prod'])
    args = parser.parse_args()
    try:
        provision(args.kubeconfig, args.environment)
    except Exception as error:
        print('CNPG Secret provisioning failed (' + type(error).__name__ + '); inspect privately', file=sys.stderr)
        sys.exit(1)
