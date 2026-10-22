#!/usr/bin/env python3
"""Validate rendered split-repository application manifests without cluster access."""
from pathlib import Path
import re
import sys
import yaml


def validate(path, environment):
    documents = [d for d in yaml.safe_load_all(Path(path).read_text()) if d]
    revisions = set()
    for name in ('backend', 'frontend'):
        deployments = [d for d in documents if d.get('kind') == 'Deployment' and d['metadata']['name'] == name]
        if len(deployments) != 1 or deployments[0]['metadata'].get('namespace') != 'app-' + environment:
            raise ValueError('Expected one environment-specific deployment per component')
        containers = [c for c in deployments[0]['spec']['template']['spec']['containers'] if c['name'] == name]
        pattern = rf'ghcr\.io/fastapi-traefik-devops/fastapi-{name}:sha-([0-9a-f]{{40}})@sha256:([0-9a-f]{{64}})'
        match = re.fullmatch(pattern, containers[0]['image']) if len(containers) == 1 else None
        if not match or match[1] == '0' * 40 or match[2] == '0' * 64:
            raise ValueError('Immutable, non-placeholder application image pair required')
        revisions.add(match[1])
    if len(revisions) != 1:
        raise ValueError('Both images must identify the same application revision')
    return len(documents)


if __name__ == '__main__':
    print('Validated resources:', validate(sys.argv[1], sys.argv[2]))
