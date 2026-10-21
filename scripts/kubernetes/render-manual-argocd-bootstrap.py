#!/usr/bin/env python3
"""Render Application/AppProject input with automated sync and pruning disabled."""

import sys

import yaml


def main():
    objects = list(yaml.safe_load_all(sys.stdin))
    if not objects:
        raise ValueError()
    for obj in objects:
        if not isinstance(obj, dict) or obj.get('kind') not in ('Application', 'AppProject'):
            raise ValueError()
        if obj.get('apiVersion') != 'argoproj.io/v1alpha1':
            raise ValueError()
        if obj['metadata'].get('namespace') != 'argocd':
            raise ValueError()
        if obj['kind'] == 'Application':
            automated = obj['spec'].setdefault('syncPolicy', {}).setdefault('automated', {})
            automated.update(enabled=False, prune=False)
    # Validate the entire input before writing anything to the apply pipeline.
    yaml.safe_dump_all(objects, sys.stdout, sort_keys=False)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Invalid Argo CD bootstrap input; no manifests rendered.', file=sys.stderr)
        sys.exit(1)
