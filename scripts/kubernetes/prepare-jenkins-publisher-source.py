#!/usr/bin/env python3
"""Prepare an immutable publisher helper bundle without executing application code."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = 'd87b3c9599c5b79dfc6b6751739a110ecbb2ba96'
SOURCE_REPOSITORY = 'fastapi-traefik-devops/fastapi-traefik-liora-application'


def git(source, *arguments):
    result = subprocess.run(['git', '-C', str(source), *arguments], capture_output=True)
    if result.returncode:
        raise RuntimeError('Required application Git object is unavailable')
    return result.stdout


def prepare(source, observer=False):
    remote = git(source, 'remote', 'get-url', 'origin').decode().strip()
    if remote not in [f'git@github.com:{SOURCE_REPOSITORY}.git',
                      f'https://github.com/{SOURCE_REPOSITORY}.git',
                      f'https://github.com/{SOURCE_REPOSITORY}']:
        raise RuntimeError('Unexpected application repository')
    resolved = git(source, 'rev-parse', SOURCE_COMMIT + '^{commit}').decode().strip()
    if resolved != SOURCE_COMMIT:
        raise RuntimeError('Unexpected application source commit')
    entries = git(source, 'ls-tree', '-r', '-z', SOURCE_COMMIT, '--', 'ci/').split(b'\0')
    data = {}
    for entry in filter(None, entries):
        metadata, path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        path = path.decode()
        name = path.removeprefix('ci/')
        if (mode not in ('100644', '100755') or kind != 'blob'
                or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in data):
            raise RuntimeError('Unsupported publisher source entry')
        content = git(source, 'cat-file', 'blob', oid)
        # Verify Git's content-addressed object before constructing the bundle.
        blob = b'blob ' + str(len(content)).encode() + b'\0' + content
        if hashlib.sha1(blob).hexdigest() != oid:
            raise RuntimeError('Publisher source integrity failure')
        data[name] = content.decode('utf-8')
    if not {'registry.py', 'phase1.py', 'candidate.py', 'promote.py', 'publish.sh',
            'promote-stage.sh', 'publisher-action.sh', 'stage_acceptance.py', 'validate_gitops.py', 'validate.sh'} <= data.keys():
        raise RuntimeError('Required publisher helpers are missing')
    if sum(len(k.encode()) + len(v.encode()) for k, v in data.items()) > 900 * 1024:
        raise RuntimeError('Publisher bundle exceeds ConfigMap budget')
    if observer:
        data = {'stage_acceptance.py': data['stage_acceptance.py']}
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'name': ('jenkins-acceptance-ci-' if observer else 'jenkins-publisher-ci-') + SOURCE_COMMIT[:12],
                         'namespace': 'jenkins-acceptance' if observer else 'jenkins-publisher',
                         'annotations': {'liora.aprt.info/source-repository': 'https://github.com/' + SOURCE_REPOSITORY,
                                         'liora.aprt.info/source-commit': SOURCE_COMMIT,
                                         'liora.aprt.info/data-sha256': digest}},
            'data': data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent / 'fastapi-traefik-liora-application')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--observer', action='store_true', help='Prepare only the read-only STAGE observer')
    args = parser.parse_args()
    os.umask(0o077)
    bundle = prepare(args.source, args.observer)
    # Exclusive creation prevents silently replacing reviewed source provenance.
    with args.output.open('x') as stream:
        json.dump(bundle, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'prepared': True, 'commit': SOURCE_COMMIT, 'files': len(bundle['data']),
                      'data_sha256': bundle['metadata']['annotations']['liora.aprt.info/data-sha256']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'prepared': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
