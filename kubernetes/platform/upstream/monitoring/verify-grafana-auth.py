#!/usr/bin/env python3
"""Verify login and all provisioned dashboard queries using a normal login session."""
import base64
import http.cookiejar
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml

kubectl = ['kubectl', '--context', 'kind-fastapi-dev', '-n', 'monitoring']
base = 'http://127.0.0.1:13001'

def request(opener, path, body=None):
    req = urllib.request.Request(base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'} if body is not None else {})
    return opener.open(req, timeout=30)

def get_json(opener, path, body=None):
    with request(opener, path, body) as response:
        assert response.status == 200
        return json.load(response)

service = json.loads(subprocess.check_output(kubectl + ['get', 'svc', 'monitoring-grafana', '-o', 'json']))
assert service['spec']['type'] == 'ClusterIP'
assert not service['spec'].get('externalIPs')
ingresses = json.loads(subprocess.check_output(kubectl + ['get', 'ingress', '-o', 'json']))
assert not ingresses['items'], 'Unexpected monitoring ingress'
subprocess.run(kubectl + ['rollout', 'status', 'deployment/monitoring-grafana', '--timeout=180s'], check=True)
secret = json.loads(subprocess.check_output(kubectl + ['get', 'secret', 'monitoring-grafana-admin', '-o', 'json']))['data']
credentials = {key: base64.b64decode(secret[field]).decode() for key, field in
               [('user', 'admin-user'), ('password', 'admin-password')]}
forward = subprocess.Popen(kubectl + ['port-forward', '--address=127.0.0.1',
                           'svc/monitoring-grafana', '13001:80'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    anonymous = urllib.request.build_opener()
    for attempt in range(30):
        try:
            get_json(anonymous, '/api/health')
            break
        except (OSError, urllib.error.URLError):
            if attempt == 29:
                raise
            time.sleep(1)
    docs = yaml.safe_load((Path(__file__).parent / 'dashboards/platform.yaml').read_text())['data']
    dashboards = [json.loads(contents) for contents in docs.values()]
    for path in ['/api/search?type=dash-db', '/api/datasources/uid/prometheus',
                 '/api/dashboards/uid/' + dashboards[0]['uid'], '/api/ds/query']:
        try:
            request(anonymous, path, {'queries': []} if path == '/api/ds/query' else None)
        except urllib.error.HTTPError as error:
            assert error.code == 401, (path, error.code)
        else:
            raise AssertionError('Anonymous access permitted: ' + path)
    with request(anonymous, '/d/' + dashboards[0]['uid']) as response:
        assert urllib.parse.urlparse(response.url).path == '/login'
    with request(anonymous, '/login') as response:
        page = response.read().decode()
        assert '"disableLoginForm":false' in page.replace(' ', '')
    print('Anonymous APIs: 401; dashboard redirects to /login; login form enabled.')
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    get_json(session, '/login', credentials)
    assert get_json(session, '/api/user')['login'] == credentials['user']
    del credentials, secret
    datasource = get_json(session, '/api/datasources/uid/prometheus')
    assert datasource['uid'] == 'prometheus'
    assert datasource['url'] == 'http://monitoring-prometheus.monitoring.svc.cluster.local:9090'
    search = get_json(session, '/api/search?type=dash-db')
    assert {item['uid'] for item in search} >= {item['uid'] for item in dashboards}
    for desired in dashboards:
        live = get_json(session, '/api/dashboards/uid/' + desired['uid'])
        assert live['meta']['provisioned'] is True
        assert live['dashboard']['panels'] == desired['panels']
        checks = 0
        for panel in live['dashboard']['panels']:
            for target in panel.get('targets', []):
                expr = target.get('expr')
                if not expr:
                    continue
                for namespace in (['app-dev', 'app-stage'] if '$namespace' in expr else ['']):
                    body = {'queries': [{'refId': 'A', 'expr': expr.replace('$namespace', namespace),
                        'instant': True, 'range': False, 'datasource': {'uid': 'prometheus', 'type': 'prometheus'},
                        'format': 'time_series', 'intervalMs': 60000, 'maxDataPoints': 100}],
                        'from': 'now-5m', 'to': 'now'}
                    result = get_json(session, '/api/ds/query', body)['results']['A']
                    assert not result.get('error'), (desired['uid'], panel['title'])
                    assert any(any(values for values in frame.get('data', {}).get('values', []))
                               for frame in result.get('frames', [])), (desired['uid'], panel['title'])
                    checks += 1
        print('Authenticated dashboard', desired['uid'], checks, 'queries returned data; panels preserved.')
    print('PASS: normal login session, Prometheus datasource, four dashboards; ClusterIP, no ingress.')
finally:
    forward.terminate()
    try:
        forward.wait(timeout=5)
    except subprocess.TimeoutExpired:
        forward.kill()
        forward.wait()
