#!/usr/bin/env python3
"""Install a held manual CI job, then request one build with a persistent retry guard."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shlex
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
JOB = 'migration-ci'
STATE = '''
import jenkins.model.Jenkins
import hudson.model.Job
import hudson.model.User
import groovy.json.JsonOutput
def digest = { text -> java.security.MessageDigest.getInstance('SHA-256').digest(text.getBytes('UTF-8')).encodeHex().toString() }
def j = Jenkins.get()
def jobs = j.getAllItems(Job.class)
println JsonOutput.toJson([quiet:j.isQuietingDown(), executors:j.numExecutors,
 queue:j.queue.items.size(), running:jobs.sum { it.builds.count { b -> b.isBuilding() } } ?: 0,
 jobs:jobs.collectEntries { [(it.fullName):[disabled:it.isDisabled(), builds:it.builds.size(),
 triggers:it.getTriggers().size()]] },
 configs:j.getAllItems().findAll { it.fullName != 'migration-ci' }.collectEntries {
 [(it.fullName):digest(it.configFile.asString())] },
 users:User.getAll().findAll { new File(it.rootDir, 'config.xml').exists() }.collectEntries {
 [(it.id):digest(new File(it.rootDir, 'config.xml').getText('UTF-8'))] }])
'''


def save(directory, name, value):
    path = directory / name
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def client():
    # Validates the original hold before returning an authenticated private client.
    return runpy.run_path(str(ROOT / 'scripts/kubernetes/deploy-jenkins-agents.py'))['held_request']()


def script(request, text):
    crumb = json.loads(request('/crumbIssuer/api/json'))
    return request('/scriptText', urllib.parse.urlencode({'script': text}).encode(),
                   {crumb['crumbRequestField']: crumb['crumb']})


def inspect(request):
    return json.loads(script(request, STATE))


def post(request, path, fields=None):
    crumb = json.loads(request('/crumbIssuer/api/json'))
    return request(path, urllib.parse.urlencode(fields or {}).encode(),
                   {crumb['crumbRequestField']: crumb['crumb']})


def hold(request):
    script(request, '''
def j = jenkins.model.Jenkins.get()
def job = j.getItemByFullName('migration-ci')
if (job != null) { job.setDisabled(true); job.save() }
j.doQuietDown()
println 'Execution hold restored'
''')


def prepare(app, directory):
    if subprocess.check_output(['git', '-C', str(app), 'status', '--porcelain']).strip():
        raise RuntimeError('Application checkout must be clean and committed')
    sha = subprocess.check_output(['git', '-C', str(app), 'rev-parse', 'HEAD'], text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise RuntimeError('Full source SHA required')
    definition = subprocess.check_output(['git', '-C', str(app), 'show', sha + ':Jenkinsfile.migration']).decode()
    request = client()
    baseline = inspect(request)
    if JOB in baseline['jobs']:
        raise RuntimeError('Manual job already exists; inspect its evidence, do not replace it')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if (directory / 'baseline.json').exists():
        if json.loads((directory / 'baseline.json').read_text()) != baseline:
            raise RuntimeError('State changed since interrupted preparation')
    else:
        save(directory, 'baseline.json', baseline)
    validation = post(request, '/pipeline-model-converter/validate', {'jenkinsfile': definition}).decode()
    if 'Jenkinsfile successfully validated' not in validation:
        raise RuntimeError('Declarative Pipeline validation failed: ' + validation[:2000])
    if not (directory / 'validation.json').exists():
        save(directory, 'validation.json', {'result': validation.strip()})
    bundle = directory / (sha + '.bundle')
    if not bundle.exists():
        subprocess.run(['git', '-C', str(app), 'bundle', 'create', str(bundle), 'HEAD'], check=True)
    subprocess.run(['git', '-C', str(app), 'bundle', 'verify', str(bundle)], check=True, capture_output=True)
    kube = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'), '-n', 'jenkins-ci']
    pods = json.loads(subprocess.check_output(kube + ['get', 'pods', '-l', 'app.kubernetes.io/name=host-ci', '-o', 'json']))['items']
    if len(pods) != 1:
        raise RuntimeError('Expected one CI worker pod')
    pod = pods[0]['metadata']['name']
    target = '/home/jenkins/agent/.migration-inputs/' + bundle.name
    # Bulk kubectl stdin was truncated on this lab server. Stream over the existing
    # administrator SSH path directly into this worker's verified local-path PVC.
    claim = json.loads(subprocess.check_output(kube + ['get', 'pvc', 'ci-work', '-o', 'json']))
    pv = json.loads(subprocess.check_output(kube[:2] + ['get', 'pv', claim['spec']['volumeName'], '-o', 'json']))
    if pv['spec']['claimRef']['namespace'] != 'jenkins-ci' or pv['spec']['claimRef']['name'] != 'ci-work':
        raise RuntimeError('Unexpected CI volume binding')
    volume_path = pv['spec']['local']['path']
    if not volume_path.startswith('/var/lib/rancher/k3s/storage/'):
        raise RuntimeError('Expected the existing local-path CI volume')
    node = json.loads(subprocess.check_output(kube[:2] + ['get', 'node', pods[0]['spec']['nodeName'], '-o', 'json']))
    address = next(a['address'] for a in node['status']['addresses'] if a['type'] == 'InternalIP')
    if address not in ['192.168.77.201', '192.168.77.202', '192.168.77.203']:
        raise RuntimeError('Expected a NONPROD worker address')
    receiver = """import hashlib, os, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = sys.stdin.buffer.read()
assert hashlib.sha256(data).hexdigest() == sys.argv[2], 'Incomplete source bundle'
path.parent.mkdir(mode=0o700, exist_ok=True)
with path.open('xb') as stream:
    stream.write(data)
os.chmod(path, 0o600)
os.chown(path, 1000, 1000)
os.chown(path.parent, 1000, 1000)
"""
    command = 'sudo -n python3 -c ' + shlex.quote(receiver) + ' ' + shlex.quote(
        volume_path + '/.migration-inputs/' + bundle.name) + ' ' + hashlib.sha256(bundle.read_bytes()).hexdigest()
    subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(ROOT / '.local-work/phase8/node-known-hosts'),
        '-i', str(ROOT / 'recovery/LIORA-id_ed25519'), 'root-admin@' + address, command],
        input=bundle.read_bytes(), check=True)
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    copied = subprocess.check_output(kube + ['exec', pod, '-c', 'agent', '--', 'sha256sum', target], text=True).split()[0]
    if copied != digest:
        raise RuntimeError('Staged bundle hash differs')
    root = ET.Element('flow-definition', {'plugin': 'workflow-job'})
    ET.SubElement(root, 'description').text = 'Approved local-only Phase 9 checkpoint; no publication or deployment.'
    ET.SubElement(root, 'keepDependencies').text = 'false'
    ET.SubElement(root, 'properties')
    node = ET.SubElement(root, 'definition', {'class': 'org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition', 'plugin': 'workflow-cps'})
    ET.SubElement(node, 'script').text = definition
    ET.SubElement(node, 'sandbox').text = 'true'
    ET.SubElement(root, 'triggers')
    ET.SubElement(root, 'disabled').text = 'true'
    crumb = json.loads(request('/crumbIssuer/api/json'))
    request('/createItem?name=' + JOB, ET.tostring(root),
            {crumb['crumbRequestField']: crumb['crumb'], 'Content-Type': 'application/xml'})
    # Parameters must exist before the first build, without executing Pipeline properties.
    script(request, '''
import hudson.model.*
def job = jenkins.model.Jenkins.get().getItemByFullName('migration-ci')
job.addProperty(new ParametersDefinitionProperty([
 new StringParameterDefinition('APP_COMMIT', '', 'Exact approved application commit'),
 new StringParameterDefinition('SOURCE_BUNDLE', '', 'Operator-staged local Git bundle')]))
job.save()
println 'Manual job installed disabled'
''')
    save(directory, 'receipt.json', {'sha': sha, 'bundle': target, 'bundle_sha256': digest,
         'definition_sha256': hashlib.sha256(definition.encode()).hexdigest(), 'job': JOB})
    print('Manual Pipeline validated; source bundle verified; job installed disabled.', flush=True)


def execute(directory):
    receipt = json.loads((directory / 'receipt.json').read_text())
    baseline = json.loads((directory / 'baseline.json').read_text())
    request = client()
    before = inspect(request)
    if before['configs'] != baseline['configs'] or before['users'] != baseline['users']:
        raise RuntimeError('Imported configuration or users changed; inspect before execution')
    if any(before['jobs'][name] != state for name, state in baseline['jobs'].items()):
        raise RuntimeError('Imported job state changed')
    definition = ET.fromstring(request('/job/migration-ci/config.xml'))
    if hashlib.sha256(definition.findtext('definition/script').encode()).hexdigest() != receipt['definition_sha256']:
        raise RuntimeError('Installed Pipeline differs from approved source')
    # Exclusive creation happens BEFORE enabling or POSTing. Never retry this operation.
    save(directory, 'request-boundary.json', {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                            'sha': receipt['sha'], 'automatic_retry': False})
    try:
        script(request, '''
def j = jenkins.model.Jenkins.get()
def job = j.getItemByFullName('migration-ci')
assert job.nextBuildNumber == 1
assert job.builds.isEmpty()
job.setDisabled(false); job.save()
j.doCancelQuietDown()
println 'Only manual CI enabled'
''')
        # Jenkins redirects to the queue URL. The held client follows it; no retry is made.
        post(request, '/job/migration-ci/buildWithParameters',
             {'APP_COMMIT': receipt['sha'], 'SOURCE_BUNDLE': receipt['bundle']})
        print('Exactly one manual build requested; monitoring migration-ci #1.', flush=True)
        deadline = time.monotonic() + 96 * 60
        last = None
        while time.monotonic() < deadline:
            job = json.loads(request('/job/migration-ci/api/json?tree=builds[number,building,result],inQueue'))
            builds = job.get('builds', [])
            if len(builds) > 1 or (builds and builds[0]['number'] != 1):
                raise RuntimeError('Unexpected build count; restore hold and inspect')
            state = builds[0] if builds else {'queued': job.get('inQueue')}
            if state != last:
                print(json.dumps(state), flush=True)
                last = state
            if builds and not builds[0]['building']:
                save(directory, 'build-result.json', json.loads(request('/job/migration-ci/1/api/json')))
                break
            time.sleep(20)
        else:
            raise RuntimeError('Monitor deadline reached; inspect #1 before any further action')
    finally:
        hold(request)
        final = inspect(request)
        save(directory, 'after.json', final)
        if final['configs'] != baseline['configs'] or final['users'] != baseline['users']:
            raise RuntimeError('Imported configuration or user hashes changed')
        if any(final['jobs'][name] != state for name, state in baseline['jobs'].items()):
            raise RuntimeError('Imported job state changed')
        if not final['quiet'] or final['queue'] or final['running'] or any(not j['disabled'] or j['triggers'] for j in final['jobs'].values()):
            raise RuntimeError('Execution is held; inspect remaining running/queued work')
        print('All jobs disabled; quiet mode restored; imported configuration and users unchanged.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('directory', type=Path, help='New private evidence directory (prepare), same directory (run)')
    parser.add_argument('--application', type=Path, default=ROOT.parent / 'fastapi-traefik-liora-application')
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'prepare':
        prepare(args.application.resolve(), args.directory.resolve())
    else:
        execute(args.directory.resolve())


if __name__ == '__main__':
    main()
