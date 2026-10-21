#!/usr/bin/env python3
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
import yaml

base = ['kubectl', '--kubeconfig=' + os.environ['kubeconfig'], '-n', os.environ['namespace']]
root = Path(os.environ['recovery_dir'])
entry = yaml.safe_load((root / 'recovery.yaml').read_text())['application_credentials'][os.environ['environment']]
assert entry['namespace'] == os.environ['namespace']
assert entry['first_superuser'] == 'admin007@liora.aprt.info'
assert entry['backend-secrets']['POSTGRES_PASSWORD'] == entry['db-secrets']['POSTGRES_PASSWORD']
for key in ['SECRET_KEY', 'FIRST_SUPERUSER_PASSWORD', 'POSTGRES_PASSWORD']:
    assert entry['backend-secrets'][key], 'Missing required credential'
assert 8 <= len(entry['backend-secrets']['FIRST_SUPERUSER_PASSWORD']) <= 40, 'Administrator password must be 8 to 40 characters'
registry = {}
for line in (root / '.env').read_text().splitlines():
    if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
        continue
    key, raw = line.removeprefix('export ').split('=', 1)
    values = shlex.split(raw, comments=True)
    if values:
        registry[key.strip()] = values[0]
assert registry['GHCR_REGISTRY'] == 'ghcr.io'
assert registry['GHCR_USERNAME'] and registry['GHCR_TOKEN']
required = {'ghcr-pull-secret', 'backend-secrets', 'db-secrets'}
existing = json.loads(subprocess.check_output(base + ['get', 'secrets', '-o', 'json']))
assert not required.intersection(s['metadata']['name'] for s in existing['items']), 'Existing application Secrets: preserve and review them'
claims = json.loads(subprocess.check_output(base + ['get', 'pvc', '-o', 'json']))
assert not claims['items'], 'Existing PVC: use the matching recovery procedure'
objects = []
for name in ['backend-secrets', 'db-secrets']:
    objects.append({'apiVersion': 'v1', 'kind': 'Secret',
                    'metadata': {'name': name, 'namespace': entry['namespace']},
                    'type': 'Opaque', 'stringData': entry[name]})
auth = base64.b64encode((registry['GHCR_USERNAME'] + ':' + registry['GHCR_TOKEN']).encode()).decode()
config = {'auths': {'ghcr.io': {'username': registry['GHCR_USERNAME'], 'password': registry['GHCR_TOKEN'], 'auth': auth}}}
objects.append({'apiVersion': 'v1', 'kind': 'Secret',
                'metadata': {'name': 'ghcr-pull-secret', 'namespace': entry['namespace']},
                'type': 'kubernetes.io/dockerconfigjson', 'stringData': {'.dockerconfigjson': json.dumps(config)}})
result = subprocess.run(base + ['apply', '--server-side', '--field-manager=liora-bootstrap', '-f', '-'],
                        input=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects}),
                        text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if result.returncode:
    raise SystemExit('Secret bootstrap failed; inspect permissions and conflicts without dumping values')
print('Three application Secrets created; values were not logged')
