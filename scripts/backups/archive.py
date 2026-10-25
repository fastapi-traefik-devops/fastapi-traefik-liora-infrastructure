"""Resolve the active WAL archive, including identities changed by recovery."""
from urllib.parse import urlparse

PLUGIN = 'barman-cloud.cloudnative-pg.io'


def parameters(cluster):
    return next(p['parameters'] for p in cluster['spec']['plugins']
                if p['name'] == PLUGIN and p.get('isWALArchiver'))


def location(cluster, store):
    params = parameters(cluster)
    if store['metadata']['name'] != params['barmanObjectName']:
        raise ValueError('ObjectStore does not match the active WAL archiver')
    uri = urlparse(store['spec']['configuration']['destinationPath'])
    if uri.scheme != 's3' or not uri.netloc or uri.query or uri.fragment:
        raise ValueError('Invalid active archive destination')
    return {'bucket': uri.netloc, 'prefix': uri.path.lstrip('/').rstrip('/') + '/',
            'server': params['serverName']}


def wal_prefix(archive, wal):
    return archive['prefix'] + archive['server'] + '/wals/' + wal[:16] + '/' + wal
