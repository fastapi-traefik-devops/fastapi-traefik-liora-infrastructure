#!/usr/bin/env python3
"""Stop the explicitly approved local legacy stack; preserve recovery inputs."""

import argparse
import base64
import datetime
import gzip
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request


CONTAINERS = ['host-jenkins', 'host-jenkins-agent', 'host-jenkins-publisher',
              'host-jenkins-docker', 'fastapi-dev-control-plane']


def docker(*arguments):
    result = subprocess.run(['docker', *arguments], capture_output=True)
    if result.returncode:
        raise RuntimeError('Docker operation failed; private diagnostics suppressed')
    return result.stdout


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def capture(container, source, path, command=None):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        process = subprocess.Popen(command or ['docker', 'exec', container, 'tar', '-cf', '-', '-C', '/', source.lstrip('/')],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            with gzip.GzipFile(fileobj=output, mode='wb') as compressed:
                shutil.copyfileobj(process.stdout, compressed, 1024 * 1024)
        finally:
            process.stdout.close()
            status = process.wait()
        if status:
            raise RuntimeError('Recovery copy failed')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stop-active', action='store_true',
                        help='Stop even with in-flight builds; requires explicit immediate-stop authorization')
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    directory = root / '.local-work/private/phase9' / ('stopped-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    if shutil.disk_usage(directory).free < 2 * 1024**3:
        raise RuntimeError('Insufficient preservation space')
    metadata = json.loads(docker('inspect', *CONTAINERS))
    private_json(directory / 'containers-before.json', metadata)
    if any(not container['State']['Running'] for container in metadata):
        raise RuntimeError('Unexpected initial container state; inspect before retrying')
    # Preserve every file/directory bind mount while its original inode is live.
    # Original paths can be absent even though the running mount remains valid.
    inputs = []
    for container in metadata:
        name = container['Name'].lstrip('/')
        if name == 'fastapi-dev-control-plane':
            continue
        for index, mount in enumerate(container['Mounts']):
            if mount['Type'] != 'bind':
                continue
            record = capture(name, mount['Destination'], directory / f'{name}-bind-{index}.tar.gz')
            record.update(container=name, source=mount['Source'], destination=mount['Destination'])
            inputs.append(record)
    private_json(directory / 'runtime-inputs.json', inputs)

    password = docker('exec', 'host-jenkins', 'cat', '/run/secrets/jenkins-admin-password').decode().strip()
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(path, method='GET', extra=None):
        headers = {'Authorization': 'Basic ' + auth, **(extra or {})}
        req = urllib.request.Request('http://127.0.0.1:8085' + path,
                                     data=b'' if method == 'POST' else None,
                                     headers=headers, method=method)
        with opener.open(req, timeout=30) as response:
            return response.read()

    crumb = json.loads(request('/crumbIssuer/api/json'))
    csrf = {crumb['crumbRequestField']: crumb['crumb']}
    request('/quietDown', 'POST', csrf)
    deadline = time.monotonic() + 600
    while True:
        state = json.loads(request('/api/json?tree=quietingDown'))
        queue = json.loads(request('/queue/api/json?tree=items[id]'))
        if queue['items']:
            snapshot = json.loads(request('/queue/api/json'))
            private_json(directory / f'queue-before-cancel-{time.time_ns()}.json', snapshot)
            for item in queue['items']:
                request('/queue/cancelItem?id=' + str(int(item['id'])), 'POST', csrf)
        computers = json.loads(request('/computer/api/json?tree=computer[executors[currentExecutable[url]],oneOffExecutors[currentExecutable[url]]]'))
        busy = sum(bool(executor.get('currentExecutable'))
                   for computer in computers['computer']
                   for executor in computer.get('executors', []) + computer.get('oneOffExecutors', []))
        if not state['quietingDown']:
            raise RuntimeError('Controller did not enter quiet mode')
        if arguments.stop_active:
            private_json(directory / 'inflight-at-stop.json', computers)
            break
        if not busy and not json.loads(request('/queue/api/json?tree=items[id]'))['items']:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Drain incomplete; controller left quiet for operator review')
        time.sleep(5)
    private_json(directory / 'stop-boundary.json', {'quiet': True, 'busy_executors': busy,
                 'queue_items': 0, 'drained': busy == 0, 'immediate_stop': arguments.stop_active})
    for name in CONTAINERS:
        docker('stop', '--time', '120', name)
        print(json.dumps({'stopped': name}), flush=True)
    after = json.loads(docker('inspect', *CONTAINERS))
    private_json(directory / 'containers-after.json', after)
    if any(container['State']['Running'] or container['State'].get('OOMKilled') for container in after):
        raise RuntimeError('Unexpected stopped state')
    if after[0]['State']['ExitCode'] == 137:
        raise RuntimeError('Controller required forced termination; inspect before claiming clean backup')
    # Check for any other running container sharing the legacy Jenkins home.
    active = docker('ps', '-q', '--filter', 'volume=host-jenkins-home').decode().strip()
    if active:
        raise RuntimeError('Legacy home still has a running container')
    # Read the retained volume through an isolated, read-only helper. Docker cp
    # cannot reliably access containers with now-missing host bind sources.
    helper = 'liora-jenkins-cold-copy-' + directory.name.removeprefix('stopped-').lower()
    command = ['docker', 'run', '--name', helper, '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--memory', '128m', '--cpus', '0.5', '--mount',
               'type=volume,source=host-jenkins-home,target=/source,readonly',
               '--entrypoint', 'tar', metadata[0]['Image'], '-cf', '-', '-C', '/source', '.']
    home = capture('host-jenkins', '/var/jenkins_home/.', directory / 'home.tar.gz', command)
    with tarfile.open(directory / 'home.tar.gz') as archive:
        names = {entry.name.removeprefix('./') for entry in archive}
    if not {'config.xml', 'secrets/master.key', 'secrets/hudson.util.Secret'} <= names:
        raise RuntimeError('Cold archive lacks required recovery state')
    manifest = {'mode': 'stopped-preservation', 'consistent': True, 'restore_tested': False,
                'containers': CONTAINERS, 'retained_copy_helper': helper,
                'inflight_executors_at_stop': busy, 'archives': [home, *inputs],
                'warning': 'Preserved stopped source; rollback must restore missing bind sources before any restart.'}
    private_json(directory / 'manifest.json', manifest)
    print(json.dumps({'backup_directory': str(directory), 'consistent': True,
                      'restore_tested': False, 'containers_stopped': len(after)}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'stop_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
