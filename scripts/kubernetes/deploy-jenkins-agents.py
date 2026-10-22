#!/usr/bin/env python3
"""Deploy bounded NONPROD CI workers while preserving the restored execution hold."""

import argparse
import base64
import datetime
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
KUBE = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage')]
URL = 'http://192.168.77.16:8085'
OWNER = {'liora.aprt.info/component': 'jenkins-agents'}


def run(arguments, data=None):
    result = subprocess.run(KUBE + arguments, input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError('Kubernetes operation failed; diagnostics retained by Kubernetes')
    return result.stdout


def save(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def apply(resource, dry_run=False):
    return run(['apply', *(['--dry-run=server'] if dry_run else []), '-f', '-'], json.dumps(resource).encode())


def copy_secret(secret, namespace, name):
    existing = json.loads(run(['-n', namespace, 'get', 'secret', name, '--ignore-not-found', '-o', 'json']) or b'null')
    if existing and (existing.get('data') != secret['data'] or existing.get('type') != secret['type']):
        raise RuntimeError('Existing target Secret differs; preserve it for review')
    if not existing:
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': namespace},
               'type': secret['type'], 'data': secret['data']})


def held_request():
    secret = json.loads(run(['-n', 'jenkins', 'get', 'secret', 'jenkins-foundation-login', '-o', 'json']))
    password = base64.b64decode(secret['data']['jenkins-admin-password']).decode()
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(path, data=None, headers=None):
        req = urllib.request.Request(URL + path, data=data,
            headers={'Authorization': 'Basic ' + auth, **(headers or {})})
        with opener.open(req, timeout=120) as response:
            return response.read()

    if json.loads(request('/whoAmI/api/json')).get('name') != 'admin':
        raise RuntimeError('Current administrator authentication failed')
    crumb = json.loads(request('/crumbIssuer/api/json'))
    script = '''
import jenkins.model.Jenkins
import hudson.model.Job
import groovy.json.JsonOutput
def j = Jenkins.get()
def jobs = j.getAllItems(Job.class)
println JsonOutput.toJson([quiet: j.isQuietingDown(), executors: j.numExecutors,
  queue: j.queue.items.size(), jobs_disabled: jobs.every { it.isDisabled() },
  running: jobs.sum { job -> job.builds.count { it.isBuilding() } } ?: 0])
'''
    report = json.loads(request('/scriptText', urllib.parse.urlencode({'script': script}).encode(),
        {crumb['crumbRequestField']: crumb['crumb']}))
    if report != {'quiet': True, 'executors': 0, 'queue': 0, 'jobs_disabled': True, 'running': 0}:
        raise RuntimeError('Controller execution hold is not intact')
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('restore_directory', type=Path, help='Accepted state-restore receipt directory')
    args = parser.parse_args()
    os.umask(0o077)
    if not (args.restore_directory / 'runtime-acceptance.json').is_file():
        raise RuntimeError('Complete the held state acceptance first')
    rendered = run(['kustomize', str(ROOT / 'kubernetes/platform/nonprod/jenkins/agents')])
    resources = list(yaml.safe_load_all(rendered))
    for resource in resources:
        if resource['kind'] == 'Deployment':
            for container in resource['spec']['template']['spec']['containers']:
                if '@sha256:' not in container['image']:
                    raise RuntimeError('Publish and pin worker images before deployment')
    bundle = runpy.run_path(str(ROOT / 'scripts/kubernetes/prepare-jenkins-publisher-source.py'))
    resources.append(bundle['prepare'](ROOT.parent / 'fastapi-traefik-liora-application'))
    held_request()
    deployment = json.loads(run(['-n', 'jenkins', 'get', 'deployment', 'jenkins', '-o', 'json']))
    volumes = deployment['spec']['template']['spec']['volumes']
    if not any(v.get('persistentVolumeClaim', {}).get('claimName') == 'jenkins-home-migrated' for v in volumes):
        raise RuntimeError('Expected the accepted migrated controller home')
    directory = ROOT / '.local-work/private/phase9' / ('agents-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    directory.mkdir(mode=0o700, parents=True)
    save(directory / 'controller-before.json', json.dumps(deployment).encode())
    save(directory / 'configuration-before.json', run(['-n', 'jenkins', 'get', 'configmap', 'jenkins-migration-hold', '-o', 'json']))
    for name in ('expected-files.json', 'current-admin.xml'):
        save(directory / name, (args.restore_directory / name).read_bytes())
    save(directory / 'desired.yaml', rendered)
    save(directory / 'publisher-source.json', json.dumps(resources[-1], indent=2).encode())
    namespaces = [r for r in resources if r['kind'] == 'Namespace' and r['metadata']['name'] != 'jenkins']
    for namespace in namespaces:
        name = namespace['metadata']['name']
        existing = json.loads(run(['get', 'namespace', name, '--ignore-not-found', '-o', 'json']) or b'null')
        if existing and not all(existing['metadata'].get('labels', {}).get(k) == v for k, v in OWNER.items()):
            raise RuntimeError('Existing namespace is not owned by this migration')
        namespace['metadata'].setdefault('labels', {}).update(OWNER)
        apply(namespace)
    for resource in resources:
        apply(resource, dry_run=True)
    print(json.dumps({'step': 'validated-agent-manifests', 'evidence': str(directory)}), flush=True)
    pull = json.loads(run(['-n', 'jenkins', 'get', 'secret', 'ghcr-pull-secret', '-o', 'json']))
    for namespace in namespaces:
        copy_secret(pull, namespace['metadata']['name'], 'ghcr-pull-secret')
    for resource in resources:
        if resource['kind'] != 'Deployment':
            apply(resource)
    controller = next(r for r in resources if r['kind'] == 'Deployment' and r['metadata']['namespace'] == 'jenkins')
    apply(controller)
    run(['-n', 'jenkins', 'rollout', 'status', 'deployment/jenkins', '--timeout=900s'])
    request = held_request()
    for name, namespace, key in [('host-ci', 'jenkins-ci', 'agent-secret'),
                                  ('registry-publisher', 'jenkins-publisher', 'publisher-secret')]:
        jnlp = ET.fromstring(request('/computer/' + name + '/jenkins-agent.jnlp'))
        arguments = jnlp.findall('.//argument')
        if not arguments or not arguments[0].text:
            raise RuntimeError('Controller did not return the inbound agent identity')
        copy_secret({'type': 'Opaque', 'data': {key: base64.b64encode(arguments[0].text.encode()).decode()}},
                    namespace, 'jenkins-inbound')
    print(json.dumps({'step': 'controller-held-worker-identities-ready'}), flush=True)
    for resource in resources:
        if resource['kind'] == 'Deployment' and resource['metadata']['namespace'] != 'jenkins':
            apply(resource)
    for namespace, name in [('jenkins-ci', 'host-ci'), ('jenkins-publisher', 'registry-publisher')]:
        run(['-n', namespace, 'rollout', 'status', 'deployment/' + name, '--timeout=900s'])
        deadline = time.monotonic() + 300
        while True:
            state = json.loads(request('/computer/' + name + '/api/json?tree=offline,numExecutors'))
            if state.get('offline') is False and state.get('numExecutors') == 1:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Worker Pod is running but Jenkins agent is not connected')
            time.sleep(2)
    held_request()
    helpers = resources[-1]['data']
    hashes = run(['-n', 'jenkins-publisher', 'exec', 'deployment/registry-publisher', '--',
                  'sha256sum', *['/opt/phase1-ci/' + name for name in helpers]])
    actual = {line.split(None, 1)[1].removeprefix('/opt/phase1-ci/'): line.split(None, 1)[0]
              for line in hashes.decode().splitlines()}
    if actual != {name: hashlib.sha256(value.encode()).hexdigest() for name, value in helpers.items()}:
        raise RuntimeError('Mounted publisher source does not match the reviewed Git objects')
    receipt = {'deployed': True, 'controller_quiet': True, 'jobs_enabled': False,
               'publication_enabled': False, 'publisher_source_commit': bundle['SOURCE_COMMIT'],
               'publisher_files_verified': len(helpers)}
    save(directory / 'deployment-receipt.json', json.dumps(receipt, indent=2).encode())
    print(json.dumps({**receipt, 'evidence': str(directory)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'deployed': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
