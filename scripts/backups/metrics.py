#!/usr/bin/env python3
"""Read-only backup/usage telemetry on VM 250; WAL metrics stay cluster-local."""
import argparse
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time

import boto3
from botocore.config import Config
from coordinator import Coordinator, load_config, cluster_name, backup_path, ANNOTATION


def timestamp(value):
    if not value:
        return 0
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def usage(client, bucket, budget=120):
    total = count = 0
    token = None
    deadline = time.monotonic() + budget
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError('Usage collection deadline exceeded')
        response = client.list_objects_v2(Bucket=bucket, **({'ContinuationToken': token} if token else {}))
        total += sum(x['Size'] for x in response.get('Contents', []))
        count += len(response.get('Contents', []))
        if not response.get('IsTruncated'):
            return total, count
        following = response.get('NextContinuationToken')
        if not following or following == token:
            raise ValueError('Invalid object-list pagination')
        token = following


def collect(config, previous=None):
    now = time.time()
    result = {'observed': now, 'environments': {}, 'usage': (previous or {}).get('usage', {})}
    c = Coordinator(config)
    try:
        lease = c.lease()
        state = json.loads(lease['metadata'].get('annotations', {}).get(ANNOTATION, '{}'))
        held = bool(lease.get('spec', {}).get('holderIdentity'))
        result['cycle'] = {'held': int(held), 'blocked': int(held and bool(state.get('blocked_at'))),
            'last_heartbeat': timestamp(lease.get('spec', {}).get('renewTime')), 'ok': 1}
    except Exception:
        result['cycle'] = {'held': 0, 'blocked': 0, 'last_heartbeat': 0, 'ok': 0}
    for env in ('prod', 'stage', 'dev'):
        try:
            backups = c.api(env).request('GET', backup_path(env))['items']
            backups = [b for b in backups if b['spec']['cluster']['name'] == 'liora-db' and b['spec']['method'] == 'plugin']
            phases = []
            for b in backups:
                status = dict(b.get('status', {}))
                status['event_time'] = status.get('stoppedAt') or status.get('reconciliationTerminatedAt') or status.get('startedAt') or b['metadata']['creationTimestamp']
                phases.append((status.get('phase', '').lower(), status))
            result['environments'][env] = {
                'success': max([timestamp(s['event_time']) for p, s in phases if p == 'completed'] or [0]),
                'failure': max([timestamp(s['event_time']) for p, s in phases if p == 'failed'] or [0]),
                'nonterminal': sum(p not in ('completed', 'failed') for p, _ in phases), 'ok': 1}
        except Exception:
            result['environments'][env] = {'success': 0, 'failure': 0, 'nonterminal': 0, 'ok': 0}
    try:
        r = config['r2']
        s3 = boto3.client('s3', endpoint_url=r['endpoint'], region_name='auto',
            aws_access_key_id=r['access_key_id'], aws_secret_access_key=r['secret_access_key'],
            config=Config(connect_timeout=10, read_timeout=20, retries={'max_attempts': 0}))
        size, objects = usage(s3, r['bucket'])
        result['usage'] = {'bytes': size, 'objects': objects, 'last_success': now, 'ok': 1}
    except Exception:
        result['usage']['ok'] = 0
    return result


def exposition(data, cluster):
    lines = []
    for env, v in data.get('environments', {}).items():
        if cluster_name(env) != cluster:
            continue
        labels = 'cluster="' + cluster + '",environment="' + env.upper() + '",namespace="app-' + env + '"'
        for suffix, key in [('last_success_timestamp','success'), ('last_failure_timestamp','failure'),
                            ('nonterminal_count','nonterminal'), ('telemetry_ok','ok')]:
            lines.append('liora_backup_' + suffix + '{' + labels + '} ' + str(v[key]))
    cycle = data.get('cycle', {})
    # The global cycle belongs to PROD; aggregate bucket usage is notified in NONPROD.
    if cluster == 'prod':
        for suffix, key in [('lease_held','held'),('blocked','blocked'),('last_heartbeat_timestamp','last_heartbeat'),('telemetry_ok','ok')]:
            lines.append('liora_backup_cycle_' + suffix + ' ' + str(cycle.get(key,0)))
    if cluster == 'nonprod':
        for suffix, key in [('bytes','bytes'),('objects','objects'),('last_success_timestamp','last_success'),('telemetry_ok','ok')]:
            lines.append('liora_r2_usage_' + suffix + ' ' + str(data.get('usage',{}).get(key,0)))
    lines.append('liora_backup_collection_timestamp ' + str(data.get('observed',0)))
    return '\n'.join(lines) + '\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default='/etc/liora-backups/config.json');p.add_argument('--once',action='store_true')
    args=p.parse_args();config=load_config(args.config)
    if args.once:
        print(json.dumps(collect(config)));return
    state = {}
    lock = threading.Lock()
    def update():
        nonlocal state
        while True:
            fresh=collect(config,state)
            with lock:state=fresh
            target=Path(config['state_dir'])/'metrics.json';temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps(fresh));temporary.chmod(0o600);temporary.replace(target)
            time.sleep(60)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ['/metrics/nonprod','/metrics/prod']:
                self.send_error(404);return
            with lock:body=exposition(state,self.path.rsplit('/',1)[-1]).encode()
            self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    threading.Thread(target=update,daemon=True).start()
    ThreadingHTTPServer((config.get('listen','192.168.77.250'),9899),Handler).serve_forever()


if __name__=='__main__':
    os.umask(0o077)
    try:main()
    except Exception as error:raise SystemExit('Backup metrics failed: '+type(error).__name__)
