#!/usr/bin/env python3
"""Connect the read-only STAGE observer to a held controller without running builds."""

import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
AGENTS = runpy.run_path(str(ROOT / 'scripts/kubernetes/deploy-jenkins-agents.py'))
run, apply, save = AGENTS['run'], AGENTS['apply'], AGENTS['save']
copy_secret, held_request = AGENTS['copy_secret'], AGENTS['held_request']
NAMESPACE, NODE, SECRET = 'jenkins-acceptance', 'stage-observer', 'stage-observer-connection'


def check_resources(resources, bundle):
    deployment = next(r for r in resources if r['kind'] == 'Deployment')
    for container in deployment['spec']['template']['spec']['containers']:
        if '@sha256:' not in container['image']:
            raise RuntimeError('Publish and pin the observer image before deployment')
    volumes = {v['name']: v for v in deployment['spec']['template']['spec']['volumes']}
    if volumes['helpers']['configMap']['name'] != bundle['metadata']['name']:
        raise RuntimeError('Observer manifest and bundle helper pin differ')
    if volumes['connection']['secret']['secretName'] != SECRET:
        raise RuntimeError('Unexpected observer connection Secret')
    if any(r['kind'] == 'Secret' for r in resources):
        raise RuntimeError('Connection Secrets are created from the controller, never from Git')
    return deployment


def install_bundle(bundle):
    name = bundle['metadata']['name']
    existing = json.loads(run(['-n', NAMESPACE, 'get', 'configmap', name, '--ignore-not-found', '-o', 'json']) or b'null')
    if not existing:
        apply(bundle)
    elif existing.get('data') != bundle['data']:
        raise RuntimeError('Existing observer bundle differs; preserve it for review')


def main():
    os.umask(0o077)
    resources = list(yaml.safe_load_all(run(['kustomize', str(ROOT / 'kubernetes/platform/nonprod/jenkins/acceptance')])))
    source = runpy.run_path(str(ROOT / 'scripts/kubernetes/prepare-jenkins-publisher-source.py'))
    bundle = source['prepare'](ROOT.parent / 'fastapi-traefik-liora-application', observer=True)
    deployment = check_resources(resources, bundle)
    request = held_request()
    directory = ROOT / '.local-work/private/phase9' / ('observer-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    directory.mkdir(mode=0o700, parents=True)
    save(directory / 'desired.yaml', yaml.safe_dump_all(resources).encode())
    save(directory / 'observer-source.json', json.dumps(bundle, indent=2).encode())
    # The namespace first, so that the server-side dry run sees it.
    for resource in resources:
        if resource['kind'] == 'Namespace':
            apply(resource)
    for resource in resources:
        apply(resource, dry_run=True)
    # The immutable bundle must exist before the Deployment that mounts it.
    install_bundle(bundle)
    copy_secret(json.loads(run(['-n', 'jenkins', 'get', 'secret', 'ghcr-pull-secret', '-o', 'json'])),
                NAMESPACE, 'ghcr-pull-secret')
    # JCasC declares the node; its inbound secret is read from the held controller only.
    jnlp = ET.fromstring(request('/computer/' + NODE + '/jenkins-agent.jnlp'))
    arguments = jnlp.findall('.//argument')
    if not arguments or not arguments[0].text:
        raise RuntimeError('Controller did not return the observer inbound identity')
    copy_secret({'type': 'Opaque', 'data': {'agent-secret': base64.b64encode(arguments[0].text.encode()).decode()}},
                NAMESPACE, SECRET)
    print(json.dumps({'step': 'observer-identity-ready', 'evidence': str(directory)}), flush=True)
    for resource in resources:
        if resource['kind'] not in ('Namespace', 'Deployment'):
            apply(resource)
    apply(deployment)
    run(['-n', NAMESPACE, 'rollout', 'status', 'deployment/' + NODE, '--timeout=600s'])
    deadline = time.monotonic() + 300
    while True:
        state = json.loads(request('/computer/' + NODE + '/api/json?tree=offline,numExecutors'))
        if state.get('offline') is False and state.get('numExecutors') == 1:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Observer Pod is running but the Jenkins node is not connected')
        time.sleep(2)
    held_request()
    hashes = run(['-n', NAMESPACE, 'exec', 'deployment/' + NODE, '--', 'sha256sum',
                  *['/opt/phase1-ci/' + name for name in bundle['data']]])
    actual = {line.split(None, 1)[1].removeprefix('/opt/phase1-ci/'): line.split(None, 1)[0]
              for line in hashes.decode().splitlines()}
    if actual != {name: hashlib.sha256(value.encode()).hexdigest() for name, value in bundle['data'].items()}:
        raise RuntimeError('Mounted observer source does not match the reviewed Git object')
    receipt = {'deployed': True, 'controller_quiet': True, 'jobs_enabled': False,
               'observer_bundle': bundle['metadata']['name'],
               'observer_source_commit': bundle['metadata']['annotations']['liora.aprt.info/source-commit'],
               'observer_files_verified': len(bundle['data'])}
    save(directory / 'deployment-receipt.json', json.dumps(receipt, indent=2).encode())
    print(json.dumps({**receipt, 'evidence': str(directory)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'deployed': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
