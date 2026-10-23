#!/usr/bin/env python3
"""Validate dashboard manifests locally and optionally query one live Prometheus read-only."""
import argparse
import json
import math
from pathlib import Path
import runpy
import statistics
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[2]
LEGACY = {'platform-nodes', 'ingress-traefik', 'gitops-argocd'}


def walk(panels):
    for panel in panels:
        yield panel
        yield from walk(panel.get('panels', []))


def interpolate(expr, environment, namespace):
    return expr.replace('${environment:regex}', environment).replace('$namespace', namespace).replace('$__rate_interval', '5m')


def run(command):
    result = subprocess.run([str(c) for c in command], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--promtool')
    parser.add_argument('--kustomize')
    parser.add_argument('--cluster', choices=['nonprod', 'prod'])
    parser.add_argument('--prometheus-url', help='Read-only live query validation for --cluster')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    assert not args.prometheus_url or args.cluster, '--cluster is required for live validation'
    assert args.prometheus_url or (args.promtool and args.kustomize), 'Provide local validation tools or a live endpoint'
    reports = []
    generated = runpy.run_path(str(ROOT / 'scripts/kubernetes/build-operations-dashboards.py'))['build']
    with tempfile.TemporaryDirectory(prefix='liora-dashboard-check-') as temporary:
        work = Path(temporary)
        for cluster in ([args.cluster] if args.cluster else ['nonprod', 'prod']):
            directory = ROOT / f'kubernetes/platform/{cluster}/monitoring'
            cms = [yaml.safe_load((directory / name).read_text()) for name in ['dashboards.yaml', 'operations-dashboard.yaml']]
            dashboards = [json.loads(raw) for cm in cms for raw in cm['data'].values()]
            expected = LEGACY | {'dev-stage-workloads' if cluster == 'nonprod' else 'prod-workloads', f'liora-{cluster}-operations'}
            assert {d['uid'] for d in dashboards} == expected and len(dashboards) == 5
            for cm in cms:
                assert cm['metadata']['labels']['grafana_dashboard'] == '1'
                assert cm['metadata']['namespace'] == 'monitoring'
                assert sum(len(v.encode()) for v in cm['data'].values()) < 950_000
            operations = next(d for d in dashboards if d['uid'].startswith('liora-'))
            assert operations == generated(cluster), 'Generated dashboard differs from its source; rebuild it'
            assert len([p for p in operations['panels'] if p['type'] == 'stat' and p['gridPos']['y'] == 0]) == 6
            expressions = []
            query_records = []
            for dashboard in dashboards:
                panels = list(walk(dashboard['panels']))
                ids = [p['id'] for p in panels]
                assert len(ids) == len(set(ids)) and all(isinstance(i, int) and i > 0 for i in ids)
                assert dashboard['schemaVersion'] == 39
                for panel in panels:
                    pos = panel['gridPos']
                    assert pos['x'] >= 0 and pos['w'] > 0 and pos['x'] + pos['w'] <= 24 and pos['h'] > 0
                    targets = panel.get('targets', [])
                    assert len({t['refId'] for t in targets}) == len(targets)
                    for target in targets:
                        assert panel.get('datasource', {}).get('uid') == 'prometheus'
                        expr = target['expr']
                        assert 'vector(0)' not in expr, 'Unconditional healthy-zero fallback'
                        assert not (cluster == 'prod' and ('app-dev' in expr or 'app-stage' in expr or 'app-(dev|stage)' in expr))
                        if dashboard is operations:
                            assert target['interval'] == '1m'
                        environments = ['dev', 'stage', 'dev|stage'] if cluster == 'nonprod' and '${environment:regex}' in expr else ['prod' if cluster == 'prod' else 'dev']
                        if '$namespace' in expr:
                            environments = ['dev', 'stage'] if cluster == 'nonprod' else ['prod']
                        for environment in environments:
                            rendered = interpolate(expr, environment, 'app-' + environment)
                            assert '$' not in rendered.replace('$1', ''), rendered
                            expressions.append(rendered)
                            query_records.append({'dashboard': dashboard['uid'], 'panel': panel['title'], 'environment': environment,
                                                  'expr': rendered, 'range': not target.get('instant', False)})
            if args.kustomize:
                resources = list(yaml.safe_load_all(run([args.kustomize, 'build', directory])))
                assert len([m for m in resources if m and m['kind'] == 'ConfigMap' and m['metadata'].get('labels', {}).get('grafana_dashboard') == '1']) == 2
            if args.promtool:
                rules = work / f'{cluster}-queries.yaml'
                rules.write_text(yaml.safe_dump({'groups': [{'name': 'dashboard-syntax', 'rules': [
                    {'record': f'dashboard_query_{i}', 'expr': expr} for i, expr in enumerate(sorted(set(expressions)))]}]}))
                run([args.promtool, 'check', 'rules', rules])
                fixtures = yaml.safe_load((ROOT / 'scripts/kubernetes/tests/operations-dashboard-queries.yaml').read_text())
                by_title = {p['title']: p for p in walk(operations['panels'])}
                for test in fixtures['tests']:
                    for case in test['promql_expr_test']:
                        case['expr'] = interpolate(by_title[case['expr']]['targets'][0]['expr'], 'dev', 'app-dev')
                    # Fixtures use DEV labels; test the NONPROD dashboard's edge cases.
                if cluster == 'nonprod':
                    fixtures['rule_files'] = []
                    fixture_path = work / 'behavior.yaml'
                    fixture_path.write_text(yaml.safe_dump(fixtures))
                    run([args.promtool, 'test', 'rules', fixture_path])
            report = {'cluster': cluster, 'dashboards': len(dashboards), 'legacy_uids_preserved': sorted(expected - {operations['uid']}),
                      'operations_uid': operations['uid'], 'operations_panels': sum(p['type'] != 'row' for p in walk(operations['panels'])),
                      'query_variants': len(query_records), 'unique_queries': len(set(expressions)), 'local_validation': 'passed' if args.promtool else 'not run in this invocation'}
            if args.prometheus_url:
                endpoint = args.prometheus_url.rstrip('/')

                def api(path, params=None):
                    url = endpoint + path + ('?' + urllib.parse.urlencode(params) if params else '')
                    with urllib.request.urlopen(url, timeout=30) as response:
                        data = json.load(response)
                    assert data['status'] == 'success', 'Prometheus rejected query'
                    return data['data']

                config = yaml.safe_load(api('/api/v1/status/config')['yaml'])
                assert config['global']['external_labels']['cluster'] == cluster, 'Wrong Prometheus cluster'
                names = api('/api/v1/label/__name__/values')
                report['special_metric_families'] = [n for n in names if n.startswith(('cnpg_', 'pg_', 'barman_', 'probe_ssl_', 'certmanager_', 'uptimerobot_', 'backup_'))]
                now = int(time.time())
                cache = {}
                observations = []
                timings = []
                for record in query_records:
                    expr = record['expr']
                    key = (expr, record['range'])
                    if key not in cache:
                        started = time.monotonic()
                        result = api('/api/v1/query', {'query': expr, 'time': now})['result']
                        samples = [item['value'][1] for item in result]
                        finite = sum(math.isfinite(float(v)) for v in samples)
                        history = api('/api/v1/query_range', {'query': expr, 'start': now-3600, 'end': now, 'step': 60})['result'] if record['range'] else []
                        elapsed = (time.monotonic() - started)*1000
                        timings.append(elapsed)
                        cache[key] = {'instant_series': len(result), 'finite_instant_series': finite,
                                      'range_series': len(history), 'elapsed_ms': round(elapsed, 2)}
                    observations.append({k: v for k, v in record.items() if k != 'expr'} | cache[key])
                expected_finite = ['Request rate', 'Replica gap', 'Critical', 'Nodes Ready',
                                   'Available replicas · backend / frontend', 'Argo CD · sync & health',
                                   'Database pod readiness · Kubernetes only', 'K3s certificate lifetime · internal only']
                for title in expected_finite:
                    found = [o for o in observations if o['dashboard'] == operations['uid'] and o['panel'] == title]
                    assert found and all(o['finite_instant_series'] for o in found), 'Critical panel lacks telemetry: ' + title
                services = api('/api/v1/query', {'query': 'count by(service)(traefik_service_requests_total)'})['result']
                report.update({'live_validation': 'passed', 'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
                               'service_labels': [s['metric']['service'] for s in services], 'queries_executed': len(cache),
                               'max_query_roundtrip_ms': round(max(timings), 2), 'median_query_roundtrip_ms': round(statistics.median(timings), 2),
                               'observations': observations})
            reports.append(report)
            print(json.dumps({k: v for k, v in report.items() if k != 'observations'}))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
