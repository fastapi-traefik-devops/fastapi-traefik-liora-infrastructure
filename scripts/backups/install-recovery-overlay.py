#!/usr/bin/env python3
"""Attach a prepared recovery bundle to one local GitOps overlay; no API writes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]


def images(objects):
    return {o['metadata']['name']: [c['image'] for c in o['spec']['template']['spec']['containers']]
            for o in objects if o.get('kind') == 'Deployment'}


def install(environment, bundle):
    overlay = ROOT / 'kubernetes/apps/liora/overlays' / environment
    target = overlay / 'recovery'
    source = bundle / 'gitops-patches'
    if target.exists():
        raise ValueError('Existing recovery configuration must be reviewed')
    docs = list(yaml.safe_load_all((bundle / 'application.yaml').read_text()))
    if any(o['metadata'].get('namespace') != 'app-' + environment for o in docs):
        raise ValueError('Bundle belongs to another environment')
    result = subprocess.run(['kubectl', 'kustomize', str(overlay)], capture_output=True, timeout=60)
    if result.returncode or images(yaml.safe_load_all(result.stdout)) != images(docs):
        raise ValueError('Render failed or application images changed; preserve concurrent changes')
    path = overlay / 'kustomization.yaml'
    original = path.read_bytes()
    value = yaml.safe_load(original)
    fragment = yaml.safe_load((source / 'kustomization-fragment.yaml').read_text())
    expected = {'resources': ['recovery/source-archive.yaml'], 'patches': [
        {'target': {'group': 'postgresql.cnpg.io', 'kind': 'Cluster', 'name': 'liora-db'}, 'path': 'recovery/cluster-patch.yaml'},
        {'target': {'group': 'barmancloud.cnpg.io', 'kind': 'ObjectStore', 'name': 'r2-backup'}, 'path': 'recovery/objectstore-patch.yaml'}]}
    if fragment != expected:
        raise ValueError('Unexpected recovery fragment')
    value.setdefault('resources', []).extend(fragment['resources'])
    value.setdefault('patches', []).extend(fragment['patches'])
    # New directory prevents overwrites. If interrupted, preserve it for review.
    target.mkdir()
    for name in ['source-archive.yaml', 'cluster-patch.yaml', 'objectstore-patch.yaml']:
        shutil.copyfile(source / name, target / name)
    if path.read_bytes() != original:
        raise ValueError('Overlay changed while preparing update; preserve both versions')
    temporary = overlay / '.kustomization-recovery.partial'
    with temporary.open('x') as stream:
        yaml.safe_dump(value, stream, sort_keys=False)
    temporary.replace(path)
    print(json.dumps({'prepared': True, 'environment': environment, 'overlay': str(overlay)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--environment', required=True, choices=['dev', 'stage', 'prod'])
    p.add_argument('--bundle', required=True, type=Path)
    args = p.parse_args()
    try:
        install(args.environment, args.bundle)
    except Exception as error:
        raise SystemExit('GitOps recovery preparation stopped (' + type(error).__name__ + '); preserve local files and inspect privately')
