#!/usr/bin/env python3
"""Check the migrated CI daemon and nested work path without running Jenkins jobs."""

import datetime
import json
from pathlib import Path
import subprocess
import sys

KUBE = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'),
        '-n', 'jenkins-ci', 'exec', 'deployment/host-ci', '-c', 'agent', '--']


def main():
    # The identifier is generated locally, never derived from an untrusted job.
    identifier = 'migration-smoke-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
    script = '''
set -eu
work=/home/jenkins/agent/ID
image=liora-migration-smoke:ID
mkdir "$work"
printf 'migration-work-path-ok\n' > "$work/proof"
docker pull busybox:1.37.0 >/dev/null
base=$(docker image inspect busybox:1.37.0 --format '{{index .RepoDigests 0}}')
printf 'FROM %s\nCOPY proof /proof\nCMD ["cat", "/proof"]\n' "$base" > "$work/Dockerfile"
docker build -t "$image" "$work" >/dev/null
result=$(docker run --rm --network none --mount "type=bind,src=$work,dst=/work,readonly" "$image" sh -c 'cmp /proof /work/proof && cat /work/proof')
test "$result" = migration-work-path-ok
docker image rm "$image" >/dev/null
rm "$work/proof" "$work/Dockerfile"
rmdir "$work"
printf 'migration-docker-build-and-bind-ok\n'
'''.replace('ID', identifier)
    result = subprocess.run(KUBE + ['sh', '-c', script], capture_output=True)
    if result.returncode or result.stdout.strip() != b'migration-docker-build-and-bind-ok':
        raise RuntimeError('Docker build/bind smoke failed; inspect the isolated smoke workspace')
    print(json.dumps({'docker_build': True, 'nested_shared_work_path': True,
                      'jenkins_jobs_executed': 0, 'application_images_published': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'verified': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
