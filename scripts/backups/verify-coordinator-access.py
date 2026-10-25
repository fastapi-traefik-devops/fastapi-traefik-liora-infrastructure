#!/usr/bin/env python3
"""Read-only check of both coordinator API identities; no database is required."""

import argparse
from pathlib import Path
import sys

from coordinator import API, backup_path, load_config


def verify(config, api_factory=API):
    for cluster, environments in (('nonprod', ('dev', 'stage')),
                                  ('prod', ('prod',))):
        api = api_factory(config['clusters'][cluster])
        for environment in environments:
            result = api.request('GET', backup_path(environment))
            if result.get('kind') != 'BackupList':
                raise ValueError('Unexpected BackupList response')
        if cluster == 'prod':
            lease = api.request('GET',
                '/apis/coordination.k8s.io/v1/namespaces/app-prod/leases/liora-backup-cycle')
            if lease.get('metadata', {}).get('name') != 'liora-backup-cycle':
                raise ValueError('Unexpected coordination Lease')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[2] /
                        'recovery/backup-coordinator.json')
    args = parser.parse_args()
    try:
        verify(load_config(args.config))
    except Exception as error:
        print('Coordinator access check stopped: ' + type(error).__name__, file=sys.stderr)
        return 1
    print('Coordinator API/RBAC read access verified for NONPROD and PROD.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
