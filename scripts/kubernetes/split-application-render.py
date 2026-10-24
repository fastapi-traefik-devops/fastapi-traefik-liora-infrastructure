#!/usr/bin/env python3
import os
from pathlib import Path
import yaml

root = Path(os.environ['render_dir'])
resources = list(yaml.safe_load_all((root / 'all.yaml').read_text()))
cnpg = any(r['kind'] == 'Cluster' and r['metadata']['name'] == 'liora-db' for r in resources)
private_adminer = any(r['kind'] == 'Service' and r['metadata']['name'] == 'adminer-private' for r in resources)
archive = any(r['kind'] == 'ObjectStore' and r['metadata']['name'] == 'r2-backup' for r in resources)
certificate = any(r['kind'] == 'Certificate' and r['metadata']['name'] == 'app-tls' for r in resources)
assert len(resources) == (11 if cnpg else 13) + int(private_adminer) + int(archive) + int(certificate)
assert {r['metadata']['namespace'] for r in resources} == {os.environ['namespace']}
groups = {name: [] for name in ['config-storage', 'database', 'prestart', 'application']}
for resource in resources:
    kind, name = resource['kind'], resource['metadata']['name']
    if kind in ['Deployment', 'Job']:
        for container in resource['spec']['template']['spec']['containers']:
            image = container['image']
            assert 'unconfigured' not in image and 'sha-' + '0' * 40 not in image, 'Select real images first'
            if name in ['backend', 'frontend', 'prestart']:
                assert '@sha256:' in image, 'Application images must be digest-pinned'
    if kind in ['ConfigMap', 'PersistentVolumeClaim', 'Certificate']:
        group = 'config-storage'
    elif (kind, name) in [('Service', 'db'), ('Deployment', 'postgres-deployment'), ('Cluster', 'liora-db'), ('ObjectStore', 'r2-backup')]:
        group = 'database'
    elif (kind, name) == ('Job', 'prestart'):
        group = 'prestart'
    else:
        group = 'application'
    groups[group].append(resource)
assert [len(groups[name]) for name in groups] == [(1 if cnpg else 3) + int(certificate), 2 + int(archive), 1, 7 + int(private_adminer)]
# The plugin configuration must exist before a Cluster requests WAL archiving.
groups['database'].sort(key=lambda r: r['kind'] != 'ObjectStore')
for name, items in groups.items():
    (root / (name + '.yaml')).write_text(yaml.safe_dump_all(items, sort_keys=False))
print('Render inspected and split; no resources applied')
