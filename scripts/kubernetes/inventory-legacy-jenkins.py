#!/usr/bin/env python3
"""Read legacy Jenkins metadata; never print credential values or configuration XML."""

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def docker(*arguments, data=None):
    result = subprocess.run(['docker', *arguments], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError('Docker read failed; private diagnostics suppressed')
    return result.stdout


def main():
    output = ROOT / '.local-work/private/phase9'
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    containers = ['host-jenkins', 'host-jenkins-agent', 'host-jenkins-publisher', 'host-jenkins-docker']
    summary = {'containers': [], 'jobs': [], 'credential_ids': [], 'plugins': []}
    for container in containers:
        data = json.loads(docker('inspect', container))[0]
        summary['containers'].append({
            'name': container, 'image': data['Config']['Image'], 'image_id': data['Image'],
            'memory_limit': data['HostConfig']['Memory'], 'cpu_nanos': data['HostConfig']['NanoCpus'],
            'privileged': data['HostConfig']['Privileged'],
            'mounts': [{key: mount[key] for key in ['Type', 'Source', 'Destination', 'RW']}
                       for mount in data['Mounts']],
        })
    # Config XML contains encrypted credentials: collect only into memory and parse identifiers.
    archive = docker('exec', 'host-jenkins', 'sh', '-c',
                     'cd /var/jenkins_home && find . -type f '
                     '\\( -name config.xml -o -name credentials.xml -o -name build.xml \\) '
                     '-not -path "./caches/*" -not -path "./plugins/*" | tar -cf - -T -')
    builds = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        for member in stream:
            if not member.isfile():
                continue
            path = member.name.removeprefix('./')
            if path.endswith('/build.xml'):
                builds += 1
                continue
            data = ET.fromstring(stream.extractfile(member).read())
            if path == 'config.xml':
                summary['controller'] = {'executors': data.findtext('numExecutors'),
                                         'security_realm': data.find('securityRealm').get('class'),
                                         'authorization_strategy': data.find('authorizationStrategy').get('class')}
            if path.startswith('jobs/') and path.endswith('/config.xml'):
                summary['jobs'].append({'path': path, 'kind': data.tag,
                                         'disabled': data.findtext('disabled'),
                                         'poll_intervals': [x.text for x in data.iter('interval')],
                                         'repository_urls': [x.text for x in data.iter('repositoryUrl')]})
            if path.endswith('credentials.xml') or path.endswith('/config.xml'):
                for credential in data.iter():
                    if 'credential' in credential.tag.lower() and credential.find('id') is not None:
                        summary['credential_ids'].append({'path': path, 'kind': credential.tag,
                                                          'id': credential.findtext('id')})
    summary['build_records'] = builds
    manifest = docker('exec', 'host-jenkins', 'cat', '/usr/share/jenkins/ref/plugins.txt')
    summary['plugin_lock_sha256'] = hashlib.sha256(manifest).hexdigest()
    summary['plugins'] = [line.split(':', 1)[0] for line in manifest.decode().splitlines()
                           if line.strip() and not line.startswith('#')]
    # Authenticate read-only API calls; neither Basic header nor password leaves this process.
    password = docker('exec', 'host-jenkins', 'cat', '/run/secrets/jenkins-admin-password').decode().strip()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    for name, path in [('queue', '/queue/api/json?tree=items[id,task[name],blocked,buildable]'),
                       ('computers', '/computer/api/json?tree=computer[displayName,offline,numExecutors,executors[currentExecutable[url]]]')]:
        request = urllib.request.Request('http://127.0.0.1:8085' + path, headers={'Authorization': 'Basic ' + auth})
        with opener.open(request, timeout=30) as response:
            summary[name] = json.load(response)
    # Hash active bind-mounted source to detect divergence without exporting its contents.
    summary['runtime_source_hashes'] = {}
    for source in ['/bootstrap/jenkins.yaml', '/bootstrap/jobs.groovy',
                   '/opt/phase1-bootstrap/Jenkinsfile', '/opt/phase1-bootstrap/Jenkinsfile.publish']:
        summary['runtime_source_hashes'][source] = hashlib.sha256(docker('exec', 'host-jenkins', 'cat', source)).hexdigest()
    target = output / 'legacy-inventory.json'
    with os.fdopen(os.open(target, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600), 'w') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'inventory': str(target), 'containers': len(summary['containers']),
                      'job_configs': len(summary['jobs']), 'build_records': builds,
                      'queue_items': len(summary['queue']['items']),
                      'busy_executors': sum(bool(e.get('currentExecutable')) for c in summary['computers']['computer']
                                            for e in c.get('executors', [])),
                      'credential_values_printed': False}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'inventory_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
