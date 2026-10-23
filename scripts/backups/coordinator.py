#!/usr/bin/env python3
"""Serialized CNPG full backups. Unknown state never releases the global fence."""
import argparse
import copy
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid

ORDER = ('prod', 'stage', 'dev')
TERMINAL = ('completed', 'failed')
PLUGIN = 'barman-cloud.cloudnative-pg.io'
ANNOTATION = 'liora.aprt.info/backup-cycle'


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


class UnsafeState(Exception):
    """Safe diagnostic; no HTTP bodies or credentials."""


class API:
    def __init__(self, profile):
        context = ssl.create_default_context(cadata=profile['ca_pem'])
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            NoRedirect(), urllib.request.HTTPSHandler(context=context))
        self.profile = profile

    def request(self, method, path, value=None, missing=False):
        request = urllib.request.Request(self.profile['server'].rstrip('/') + path,
            method=method, data=json.dumps(value).encode() if value is not None else None,
            headers={'Authorization': 'Bearer ' + self.profile['token'], 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise UnsafeState('Kubernetes API HTTP ' + str(error.code)) from None
        except Exception:
            raise UnsafeState('Kubernetes API outcome unknown') from None


def cluster_name(environment):
    return 'prod' if environment == 'prod' else 'nonprod'


def backup_path(environment, name=''):
    return '/apis/postgresql.cnpg.io/v1/namespaces/app-' + environment + '/backups' + ('/' + name if name else '')


class Coordinator:
    def __init__(self, config, apis=None, sleep=time.sleep, clock=time.monotonic):
        self.config = config
        self.apis = apis or {name: API(p) for name, p in config['clusters'].items()}
        self.sleep, self.clock = sleep, clock
        self.control = self.apis['prod']
        self.lease_path = '/apis/coordination.k8s.io/v1/namespaces/app-prod/leases/liora-backup-cycle'

    def api(self, environment):
        return self.apis[cluster_name(environment)]

    def alert(self, name, environment='prod', resolved=False):
        # Same stable labels as the Prometheus rules; no daily success messages.
        profile = self.config['clusters'][cluster_name(environment)]
        labels = {'alertname': name, 'cluster': cluster_name(environment),
                  'environment': environment.upper(), 'namespace': 'app-' + environment, 'severity': 'critical'}
        now = dt.datetime.now(dt.timezone.utc)
        value = [{'labels': labels, 'annotations': {
            'summary': 'CNPG backup requires operator attention',
            'description': 'Inspect the durable coordinator Lease and named Backup; never clear unknown work blindly.',
            'action': 'Use coordinator inspect/resume and runbook 19.'},
            'startsAt': (now - dt.timedelta(seconds=1)).isoformat(),
            'endsAt': (now if resolved else now + dt.timedelta(hours=26)).isoformat()}]
        try:
            req = urllib.request.Request(profile['alertmanager'] + '/api/v2/alerts',
                data=json.dumps(value).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=15) as response:
                if response.status != 200:
                    raise UnsafeState('Alertmanager rejected event')
        except Exception:
            # Prometheus independently observes the retained Lease/Backup state.
            print(json.dumps({'notification': 'Alertmanager delivery unavailable', 'alert': name}), flush=True)

    def lease(self):
        value = self.control.request('GET', self.lease_path)
        if value is None:
            raise UnsafeState('Precreated coordination Lease is required')
        return value

    def save(self, lease, state, holder):
        value = copy.deepcopy(lease)
        value['spec'] = {'holderIdentity': holder, 'renewTime': stamp()}
        value['metadata'].setdefault('annotations', {})[ANNOTATION] = json.dumps(state, separators=(',', ':'))
        # Optimistic concurrency: a lost/conflicting update stops before any new work.
        return self.control.request('PUT', self.lease_path, value)

    def active_backups(self, allowed=None):
        found = []
        for environment in ORDER:
            result = self.api(environment).request('GET', backup_path(environment))
            for backup in result['items']:
                if backup['spec']['cluster']['name'] != 'liora-db':
                    continue
                name = backup['metadata']['name']
                if (environment, name) == allowed:
                    continue
                if backup.get('status', {}).get('phase', '').lower() not in TERMINAL:
                    found.append((environment, name))
        return found

    def run(self, environments=ORDER, resume=False, timeout=7200):
        lease = self.lease()
        holder = lease.get('spec', {}).get('holderIdentity', '')
        if resume:
            if not holder:
                raise UnsafeState('No held cycle to resume')
            state = json.loads(lease['metadata']['annotations'][ANNOTATION])
            if state.get('owner_session') != holder:
                raise UnsafeState('Lease holder and journal differ')
            renewed = dt.datetime.fromisoformat(lease['spec']['renewTime'].replace('Z', '+00:00'))
            if not state.get('blocked_at') and (dt.datetime.now(dt.timezone.utc) - renewed).total_seconds() < 120:
                raise UnsafeState('An active session holds the cycle; resume is not a concurrent execution option')
            holder = uuid.uuid4().hex
            state['owner_session'] = holder
            state.pop('blocked_at', None)
            lease = self.save(lease, state, holder)
        else:
            if holder:
                existing = json.loads(lease['metadata'].get('annotations', {}).get(ANNOTATION, '{}'))
                renewed = dt.datetime.fromisoformat(lease['spec']['renewTime'].replace('Z', '+00:00'))
                if existing.get('blocked_at') or (dt.datetime.now(dt.timezone.utc) - renewed).total_seconds() > 120:
                    self.alert('CNPGBackupCycleBlocked')
                raise UnsafeState('A cycle holds the fence; wait for its owner or inspect/explicitly resume')
            if self.active_backups():
                self.alert('CNPGBackupCycleBlocked')
                raise UnsafeState('An existing nonterminal Backup blocks a new cycle')
            holder = uuid.uuid4().hex
            state = {'id': holder, 'owner_session': holder, 'started_at': stamp(), 'steps': [
                {'environment': env, 'name': 'bk-' + holder[:24] + '-' + env, 'phase': 'planned'}
                for env in ORDER if env in environments]}
            if not state['steps']:
                raise UnsafeState('No environments selected')
            lease = self.save(lease, state, holder)
        try:
            for step in state['steps']:
                environment, name = step['environment'], step['name']
                if step['phase'] in TERMINAL:
                    continue
                if self.active_backups(allowed=(environment, name)):
                    raise UnsafeState('Another nonterminal Backup blocks advancement')
                path = backup_path(environment, name)
                if step['phase'] == 'planned':
                    step['phase'] = 'creating'
                    lease = self.save(lease, state, holder)  # Durable intent BEFORE POST.
                    backup = {'apiVersion': 'postgresql.cnpg.io/v1', 'kind': 'Backup',
                        'metadata': {'name': name, 'namespace': 'app-' + environment,
                                     'labels': {'liora.aprt.info/cycle': state['id']}},
                        'spec': {'cluster': {'name': 'liora-db'}, 'method': 'plugin', 'target': 'primary',
                                 'pluginConfiguration': {'name': PLUGIN}}}
                    self.api(environment).request('POST', backup_path(environment), backup)
                deadline = self.clock() + timeout
                heartbeat = self.clock()
                while True:
                    backup = self.api(environment).request('GET', path, missing=True)
                    if not backup:
                        raise UnsafeState('Recorded creation has no observable Backup; do not recreate automatically')
                    if (backup['spec']['cluster']['name'] != 'liora-db' or
                        backup['metadata'].get('labels', {}).get('liora.aprt.info/cycle') != state['id']):
                        raise UnsafeState('Recorded Backup identity mismatch')
                    phase = backup.get('status', {}).get('phase', '').lower()
                    if phase in TERMINAL:
                        step.update(phase=phase, finished_at=stamp(),
                                    backup_status={k: v for k, v in backup.get('status', {}).items() if k in
                                        ['phase', 'backupId', 'startedAt', 'stoppedAt', 'beginWal', 'endWal', 'beginLSN', 'endLSN', 'serverName']})
                        lease = self.save(lease, state, holder)
                        print(json.dumps({'environment': environment, 'backup': name, 'phase': phase}), flush=True)
                        if phase == 'failed':
                            self.alert('CNPGFullBackupFailed', environment)
                        break
                    if self.clock() >= deadline:
                        raise UnsafeState('Backup remains running or unknown at observation deadline')
                    if self.clock() - heartbeat >= 30:
                        lease = self.save(lease, state, holder)
                        heartbeat = self.clock()
                    self.sleep(5)
            state['finished_at'] = stamp()
            lease = self.save(lease, state, '')
            if resume:
                self.alert('CNPGBackupCycleBlocked', resolved=True)
            return state
        except BaseException:
            try:
                current = self.lease()
                if current.get('spec', {}).get('holderIdentity') == holder:
                    state['blocked_at'] = stamp()
                    self.save(current, state, holder)
            except Exception:
                pass  # The last durable intent/fence remains authoritative.
            self.alert('CNPGBackupCycleBlocked')
            # No finally-release: interruption/unknown outcome must retain the fence.
            raise


def load_config(path):
    data = json.loads(Path(path).read_text())
    if data.get('version') != 1 or set(data['clusters']) != {'nonprod', 'prod'}:
        raise UnsafeState('Unsupported coordinator configuration')
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['run', 'resume', 'inspect'])
    p.add_argument('--config', default='/etc/liora-backups/config.json')
    p.add_argument('--environment', choices=ORDER)
    p.add_argument('--timeout', type=int, default=7200)
    p.add_argument('--state-dir', help='Local lock/evidence directory on another trusted operator machine')
    args = p.parse_args()
    config = load_config(args.config)
    directory = Path(args.state_dir or config.get('state_dir', '/var/lib/liora-backups'))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / 'cycle.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UnsafeState('Another local coordinator is active') from None
        c = Coordinator(config)
        if args.action == 'inspect':
            lease = c.lease()
            print(json.dumps({'holder': lease.get('spec', {}).get('holderIdentity'),
                              'journal': json.loads(lease['metadata'].get('annotations', {}).get(ANNOTATION, '{}'))}))
        else:
            result = c.run([args.environment] if args.environment else ORDER,
                           resume=args.action == 'resume', timeout=args.timeout)
            target = directory / ('cycle-' + result['id'] + '.json')
            target.write_text(json.dumps(result, indent=2));target.chmod(0o600)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except Exception as error:
        # Unknown exceptions can contain authenticated request data.
        print('Coordinator stopped: ' + (str(error) if isinstance(error, UnsafeState) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
