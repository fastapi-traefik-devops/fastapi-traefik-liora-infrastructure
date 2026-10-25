#!/usr/bin/env python3
"""Add one reviewed backend reconnect annotation without touching image pins."""

import argparse
from pathlib import Path
import re
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]


def prepare(repo, environment, change_id):
    if not re.fullmatch(r'\d{8}T\d{6}Z', change_id):
        raise ValueError('Use a UTC change ID such as 20261025T120000Z')
    overlay = repo / 'kubernetes/apps/liora/overlays' / environment
    kustomization = overlay / 'kustomization.yaml'
    content = kustomization.read_text()
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict) or list(parsed)[-1] != 'patches' or not isinstance(parsed['patches'], list):
        raise ValueError('Expected patches to be the final Kustomization field')
    marker = 'db-reconnect-patch.yaml'
    if any(isinstance(item, dict) and item.get('path') == marker for item in parsed['patches']):
        raise ValueError('Reconnect patch already selected; inspect it before another change')
    patch = overlay / marker
    if patch.exists():
        raise ValueError('Reconnect patch already exists; inspect it before another change')
    document = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
                'metadata': {'name': 'backend'},
                'spec': {'template': {'metadata': {'annotations':
                    {'liora.aprt.info/db-reconnect': change_id}}}}}
    patch.write_text(yaml.safe_dump(document, sort_keys=False))
    try:
        kustomization.write_text(content.rstrip() + '\n- path: ' + marker + '\n')
    except BaseException:
        patch.unlink()
        raise
    print('Prepared backend reconnect patch for ' + environment + '; review diff before publishing.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--environment', choices=('dev', 'stage', 'prod'), required=True)
    parser.add_argument('--change-id', required=True)
    args = parser.parse_args()
    try:
        prepare(args.repo, args.environment, args.change_id)
    except (OSError, ValueError) as error:
        print('Reconnect preparation stopped: ' + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
