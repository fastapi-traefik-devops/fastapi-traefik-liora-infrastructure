#!/usr/bin/env python3
"""Read-only source/live alert audit; never fetch Secrets or receiver configuration."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[2]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(url):
    with OPENER.open(url, timeout=25) as response:
        return json.load(response)


def audit(cluster):
    vip = '16' if cluster == 'nonprod' else '17'
    base = 'http://192.168.77.' + vip
    config = Path.home() / '.kube' / ('config-dev-stage' if cluster == 'nonprod' else 'config-prod')
    result = {'cluster': cluster, 'issues': [], 'rule_groups': [], 'metrics': {}}
    groups = get(base + ':9090/api/v1/rules')['data']['groups']
    expected = {}
    for section in ['monitoring', 'backup-monitoring']:
        source = yaml.safe_load((ROOT / f'kubernetes/platform/{cluster}/{section}/rules.yaml').read_text())
        live = subprocess.run(['kubectl', '--kubeconfig=' + str(config), '--request-timeout=30s',
                               '-n', 'monitoring', 'get', 'prometheusrule', source['metadata']['name'], '-o', 'json'],
                              capture_output=True, timeout=45, check=True)
        if json.loads(live.stdout)['spec'] != source['spec']:
            result['issues'].append('Rule source/live resource mismatch: ' + section)
        expected.update({g['name']: len(g['rules']) for g in source['spec']['groups']})
    for group in groups:
        rules = [{'name': r.get('name'), 'query': r.get('query'), 'state': r.get('state'),
                  'health': r.get('health'), 'last_error': r.get('lastError', '')} for r in group['rules']]
        result['rule_groups'].append({'name': group['name'], 'rules': rules})
        if expected.get(group['name']) != len(rules):
            result['issues'].append('Unexpected rule inventory: ' + group['name'])
        if any(r['health'] != 'ok' or r['last_error'] for r in rules):
            result['issues'].append('Rule evaluation error: ' + group['name'])
    if set(expected) != {g['name'] for g in groups}:
        result['issues'].append('Missing or unexpected rule group')
    targets = get(base + ':9090/api/v1/targets')['data']['activeTargets']
    result['targets'] = [{'job': t['labels'].get('job'), 'instance': t['labels'].get('instance'),
                          'health': t['health'], 'last_error': t.get('lastError', '')} for t in targets]
    if not targets or any(t['health'] != 'up' for t in targets):
        result['issues'].append('Unhealthy scrape target')
    result['prometheus_alerts'] = get(base + ':9090/api/v1/alerts')['data']['alerts']
    result['alertmanager_alerts'] = get(base + ':9093/api/v2/alerts')
    if result['prometheus_alerts']:
        result['issues'].append('Prometheus has firing or pending conditions; inspect their cause')
    if any(a.get('status', {}).get('state') == 'active' for a in result['alertmanager_alerts']):
        result['issues'].append('Alertmanager still has active conditions; inspect their source')
    queries = ['liora_backup_telemetry_ok', 'liora_backup_cycle_blocked', 'liora_backup_cycle_telemetry_ok',
               'liora_backup_last_success_timestamp', 'certmanager_certificate_expiration_timestamp_seconds{name="app-tls"}',
               'certmanager_certificate_ready_status{name="app-tls",condition="True"}',
               'sum(increase(alertmanager_notifications_failed_total{integration="slack"}[10m]))',
               'sum(alertmanager_notifications_total{integration="slack"})',
               'sum(increase(prometheus_notifications_errors_total[10m]))']
    for query in queries:
        data = get(base + ':9090/api/v1/query?' + urllib.parse.urlencode({'query': query}))
        result['metrics'][query] = data['data']['result']
    for env in (['dev', 'stage'] if cluster == 'nonprod' else ['prod']):
        samples = result['metrics']['liora_backup_telemetry_ok']
        matching = [s for s in samples if s['metric'].get('namespace') == 'app-' + env
                    and s['metric'].get('environment') == env.upper() and s['value'][1] == '1']
        if len(matching) != 1:
            result['issues'].append('Backup telemetry namespace/health mismatch: ' + env)
    result['verified_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=['nonprod', 'prod', 'both'], default='both')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for cluster in (['nonprod', 'prod'] if args.cluster == 'both' else [args.cluster]):
        try:
            results.append(audit(cluster))
        except Exception as error:
            results.append({'cluster': cluster, 'issues': ['Audit failed: ' + type(error).__name__]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    for result in results:
        print(json.dumps({'cluster': result['cluster'], 'issues': result['issues'],
                          'rules': sum(len(g['rules']) for g in result.get('rule_groups', [])),
                          'targets': len(result.get('targets', []))}))
    return int(any(r['issues'] for r in results))


if __name__ == '__main__':
    sys.exit(main())
