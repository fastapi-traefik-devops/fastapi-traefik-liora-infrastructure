#!/usr/bin/env python3
"""Create a private ONLINE Jenkins preservation copy; never claim consistency.

This helper does not pause jobs, stop containers or restore anything. A final
consistent cutover backup needs a separately reviewed quiesce/stop procedure.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def main():
    root = Path(__file__).resolve().parents[2]
    directory = root / '.local-work/private/phase9' / ('online-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    assert shutil.disk_usage(directory).free >= 2 * 1024**3, 'Need at least 2GiB free for this preservation copy'
    archives = []
    sources = [('home.tar.gz', ['tar', '-czf', '-', '-C', '/var/jenkins_home', '.']),
               ('runtime-inputs.tar.gz', ['tar', '-czf', '-', '/run/secrets', '/bootstrap',
                                           '/opt/phase1-bootstrap/Jenkinsfile', '/opt/phase1-bootstrap/Jenkinsfile.publish'])]
    for name, command in sources:
        target = directory / name
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            result = subprocess.run(['docker', 'exec', 'host-jenkins', *command], stdout=stream,
                                    stderr=subprocess.PIPE)
        # GNU/BusyBox tar may report changing files in an online home. Retain but label it.
        if result.returncode not in (0, 1):
            raise RuntimeError('Archive creation failed; keep private partial output for inspection')
        with tarfile.open(target, 'r:gz') as archive:
            names = {member.name.removeprefix('./').lstrip('/') for member in archive}
        required = ({'config.xml', 'secrets/master.key', 'secrets/hudson.util.Secret'}
                    if name == 'home.tar.gz' else
                    {'run/secrets/jenkins-admin-password', 'run/secrets/github-ci-app-key',
                     'run/secrets/github-gitops-app-key', 'bootstrap/jenkins.yaml', 'bootstrap/jobs.groovy',
                     'opt/phase1-bootstrap/Jenkinsfile', 'opt/phase1-bootstrap/Jenkinsfile.publish'})
        assert required <= names, 'Required recovery material missing from archive'
        digest = hashlib.sha256()
        with target.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        archives.append({'file': name, 'bytes': target.stat().st_size, 'sha256': digest.hexdigest(),
                         'members': len(names), 'tar_exit_code': result.returncode})
    manifest = {'mode': 'online-preservation-only', 'consistent': False,
                'restore_tested': False, 'source_controller': 'host-jenkins',
                'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'archives': archives,
                'excluded': ['CI/publisher workspaces', 'Docker build cache', 'running build consistency'],
                'warning': 'Jobs were not paused. Do not use this as the final cutover backup.'}
    with os.fdopen(os.open(directory / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'backup_directory': str(directory), 'archives': len(archives),
                      'archive_bytes': sum(a['bytes'] for a in archives), 'consistent': False,
                      'restore_tested': False, 'credential_values_printed': False}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'backup_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
