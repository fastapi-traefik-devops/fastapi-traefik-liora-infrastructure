#!/usr/bin/env python3
"""Validate a private Cloudflare token and optionally provision both clusters.

No token is passed through command arguments or printed in diagnostics.
The API check verifies zone visibility; successful DNS-01 issuance must verify
DNS write permission separately. This helper does not change token permissions.
"""
import argparse
import json
from pathlib import Path
import stat
import subprocess
import sys
import urllib.request


def read_token(path):
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError('Private file permissions required')
    token = path.read_text().strip()
    if not token or token.startswith('REPLACE_') or any(ord(c) <= 32 or ord(c) >= 127 for c in token):
        raise ValueError('Invalid token file')
    return token


def check_zone(token):
    request = urllib.request.Request(
        'https://api.cloudflare.com/client/v4/zones?name=aprt.info',
        headers={'Authorization': 'Bearer ' + token},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not result.get('success') or not any(x.get('name') == 'aprt.info' for x in result.get('result', [])):
        raise ValueError('Required zone unavailable')


def provision(token, kubeconfig, expected_server):
    base = ['kubectl', '--kubeconfig=' + str(kubeconfig), '--request-timeout=30s']
    result = subprocess.run(base + ['config', 'view', '--minify', '-o',
                                  'jsonpath={.clusters[0].cluster.server}'],
                            capture_output=True, text=True, timeout=45)
    if result.returncode or result.stdout != expected_server:
        raise ValueError('Unexpected Kubernetes endpoint')
    obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': 'cloudflare-dns-token', 'namespace': 'cert-manager'},
        'type': 'Opaque', 'stringData': {'api-token': token}}
    # Server-side apply avoids an additional plaintext last-applied annotation.
    result = subprocess.run(base + ['apply', '--server-side',
                                   '--field-manager=liora-cloudflare-dns', '-f', '-'],
                            input=json.dumps(obj), capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Secret provisioning failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--token-file', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'recovery/cloudflare-dns-token')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--cluster', choices=['nonprod', 'prod', 'both'], default='both')
    args = parser.parse_args()
    try:
        token = read_token(args.token_file)
        check_zone(token)
        if args.apply:
            for cluster, suffix, vip in [('nonprod', 'dev-stage', '11'), ('prod', 'prod', '12')]:
                if args.cluster in ['both', cluster]:
                    provision(token, Path.home() / '.kube' / ('config-' + suffix),
                              'https://192.168.77.' + vip + ':6443')
                    print(cluster + ': DNS credential provisioned; values withheld')
        else:
            print('DNS credential validated and aprt.info visible; DNS write permission requires issuance verification')
        return 0
    except Exception as error:
        print('DNS credential bootstrap failed: ' + type(error).__name__ + '; values withheld', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
