#!/usr/bin/env python3
"""Read GitHub App installation access with runtime Jenkins keys; never print keys/JWTs."""

import base64
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def main():
    root = Path(__file__).resolve().parents[2]
    def read(name):
        result = subprocess.run(['docker', 'exec', 'host-jenkins', 'cat', '/run/secrets/' + name],
                                capture_output=True)
        if result.returncode:
            raise RuntimeError('Cannot read runtime GitHub App input')
        return result.stdout.strip()
    def encoded(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')
    repositories = ['fastapi-traefik-liora-application', 'fastapi-traefik-liora-infrastructure',
                    'fastapi-traefik-datascientest-project']
    summary = []
    for role in ['ci', 'gitops']:
        app_id = read('github-' + role + '-app-id').decode()
        key = serialization.load_pem_private_key(read('github-' + role + '-app-key'), password=None)
        now = int(time.time())
        header = encoded(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
        claims = encoded(json.dumps({'iat': now - 60, 'exp': now + 540, 'iss': app_id}).encode())
        unsigned = header + b'.' + claims
        signature = key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
        token = (unsigned + b'.' + encoded(signature)).decode()
        for repo in repositories:
            request = urllib.request.Request('https://api.github.com/repos/fastapi-traefik-devops/' + repo + '/installation',
                                             headers={'Authorization': 'Bearer ' + token,
                                                      'Accept': 'application/vnd.github+json',
                                                      'User-Agent': 'liora-phase9-read-only-audit'})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = json.load(response)
                    summary.append({'role': role, 'repository': repo, 'status': response.status,
                                    'permissions': data['permissions'],
                                    'repository_selection': data['repository_selection']})
            except urllib.error.HTTPError as error:
                summary.append({'role': role, 'repository': repo, 'status': error.code,
                                'installation_access_verified': False})
    target = root / '.local-work/private/phase9/github-app-access.json'
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'access_check_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
