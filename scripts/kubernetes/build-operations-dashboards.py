#!/usr/bin/env python3
"""Build the two classic-schema Operations dashboard ConfigMaps. No cluster writes."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DS = {'type': 'prometheus', 'uid': 'prometheus'}


class Dumper(yaml.SafeDumper):
    pass


Dumper.add_representer(str, lambda d, s: d.represent_scalar(
    'tag:yaml.org,2002:str', s, style='|' if '\n' in s else None))


def build(cluster):
    nonprod = cluster == 'nonprod'
    environment = '${environment:regex}' if nonprod else 'prod'
    namespace = f'app-({environment})' if nonprod else 'app-prod'
    service = f'app-({environment})-(backend|frontend)-80@kubernetes'
    selector = f'namespace=~"{namespace}"'
    workloads = selector + ',deployment=~"backend|frontend"'
    ingress = f'service=~"{service}"'
    app = f'name=~"{namespace}"'
    observed = 'max(up{job="monitoring-prometheus",endpoint="http-web"} == 1)'
    total = f'sum(rate(traefik_service_requests_total{{{ingress}}}[$__rate_interval]))'

    def http_rate(code, by=''):
        group = f' by({by})' if by else ''
        base = f'sum{group}(rate(traefik_service_requests_total{{{ingress}}}[$__rate_interval]))'
        errors = f'sum{group}(rate(traefik_service_requests_total{{{ingress},code=~"{code}"}}[$__rate_interval]))'
        return f'({errors} or (0 * {base}))'

    def latency(q, by=''):
        labels = 'le' + (',' + by if by else '')
        return f'histogram_quantile({q},sum by({labels})(rate(traefik_service_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))'

    def alerts(severity):
        return f'(sum(ALERTS{{alertstate="firing",severity="{severity}",purpose!="test"}}) or (0 * {observed}))'

    desired = f'max by(namespace,deployment)(kube_deployment_spec_replicas{{{workloads}}})'
    available = f'max by(namespace,deployment)(kube_deployment_status_replicas_available{{{workloads}}})'
    missing = f'clamp_min({desired} - ({available} or on(namespace,deployment) (0 * {desired})),0)'
    ready = 'sum(max by(node)(kube_node_status_condition{condition="Ready",status="true"})) / count(max by(node)(kube_node_info))'
    panels = []
    next_id = 0
    y = 0

    def panel(title, description, kind, queries, x, py, w, h, unit='short', thresholds=None, legends=None, instant=False):
        nonlocal next_id
        next_id += 1
        defaults = {'unit': unit, 'noValue': 'No telemetry', 'decimals': 0 if unit == 'short' else 1 if unit == 'percentunit' else 2,
                    'color': {'mode': 'palette-classic'},
                    'thresholds': {'mode': 'absolute', 'steps': thresholds or [{'color': 'green', 'value': None}]}}
        result = {'id': next_id, 'title': title, 'description': description, 'type': kind,
                  'gridPos': {'x': x, 'y': py, 'w': w, 'h': h}, 'datasource': DS, 'interval': '1m',
                  'targets': [{'refId': chr(65+i), 'expr': expr, 'legendFormat': (legends or [])[i] if legends else title,
                               'instant': instant, 'range': not instant, 'interval': '1m',
                               'format': 'table' if kind == 'table' else 'time_series'}
                              for i, expr in enumerate(queries)],
                  'fieldConfig': {'defaults': defaults, 'overrides': []}}
        if kind == 'stat':
            defaults['color'] = {'mode': 'thresholds'}
            result['options'] = {'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '', 'values': False},
                                 'colorMode': 'value', 'graphMode': 'none', 'justifyMode': 'center',
                                 'textMode': 'auto', 'wideLayout': True, 'textSize': {'value': 38}}
        elif kind == 'timeseries':
            defaults['custom'] = {'drawStyle': 'line', 'lineWidth': 2, 'fillOpacity': 9, 'showPoints': 'never',
                                  'spanNulls': False, 'axisCenteredZero': False,
                                  'axisSoftMin': 0,
                                  'thresholdsStyle': {'mode': 'off'}}
            if unit in ['short', 'percentunit']:
                defaults['custom']['axisSoftMax'] = 1
            result['options'] = {'tooltip': {'mode': 'multi', 'sort': 'desc'},
                                 'legend': {'displayMode': 'list', 'placement': 'bottom', 'showLegend': True}}
        elif kind == 'bargauge':
            defaults['color'] = {'mode': 'thresholds'}
            defaults['min'] = 0
            if unit == 'percentunit':
                defaults['max'] = 1
            result['options'] = {'orientation': 'horizontal', 'displayMode': 'basic', 'showUnfilled': True,
                                 'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '', 'values': False}}
        elif kind == 'table':
            result['options'] = {'showHeader': True, 'cellHeight': 'sm', 'footer': {'show': False}}
        return result

    def row(title, collapsed=False):
        nonlocal next_id, y
        next_id += 1
        r = {'id': next_id, 'type': 'row', 'title': title, 'collapsed': collapsed,
             'gridPos': {'x': 0, 'y': y, 'w': 24, 'h': 1}, 'panels': []}
        panels.append(r)
        y += 1
        return r['panels'] if collapsed else panels

    bad_high = [{'color': 'green', 'value': None}, {'color': 'red', 'value': 1}]
    saturation = [{'color': 'green', 'value': None}, {'color': 'yellow', 'value': 0.8}, {'color': 'red', 'value': 0.95}]
    kpis = [
        ('Request rate', 'Selected application services only. Zero means observed counters with no requests; missing counters remain No telemetry.', total, 'reqps', [{'color': 'blue', 'value': None}]),
        ('HTTP 5xx', 'Selected application 5xx / total requests. No traffic produces no ratio, not a false healthy zero.', f'{http_rate("5..")} / ({total} > 0)', 'percentunit', [{'color': 'green', 'value': None}, {'color': 'yellow', 'value': 0.01}, {'color': 'red', 'value': 0.05}]),
        ('p95 latency', 'Selected application service histogram estimate. No requests can yield NaN / no value; this is not a successful health check.', latency(0.95), 's', [{'color': 'green', 'value': None}, {'color': 'yellow', 'value': 0.3}, {'color': 'red', 'value': 1}]),
        ('Replica gap', 'Backend/frontend desired minus available. Missing availability counts as unavailable. The KPI is suppressed unless desired-deployment series cover two workloads per observed Argo environment application; incomplete inventory is not healthy zero.', f'sum({missing}) and on() (count({desired}) == 2 * count(max by(name)(argocd_app_info{{{app}}})))', 'short', bad_high),
        ('Critical', 'Firing critical Prometheus alerts across this entire cluster, including shared platform; independent of Environment selection. Synthetic test alerts excluded.', alerts('critical'), 'short', bad_high),
        ('Nodes Ready', 'Ready nodes / known nodes in this cluster. A missing Ready series for a known node lowers the fraction. No node inventory means no telemetry.', ready, 'percentunit', [{'color': 'red', 'value': None}, {'color': 'yellow', 'value': 0.99}, {'color': 'green', 'value': 1}]),
    ]
    for i, (title, desc, expr, unit, thresholds) in enumerate(kpis):
        p = panel(title, desc, 'stat', [expr], i*4, 0, 4, 5, unit, thresholds, instant=True)
        if i in [1, 2]:
            p['fieldConfig']['defaults']['noValue'] = 'No traffic / telemetry'
        panels.append(p)
    y = 5
    row('01  /  Traffic, errors & latency · RED')
    panels.append(panel('Requests by Traefik service', 'Actual service labels from this cluster; no router/entrypoint traffic from unrelated platform routes.', 'timeseries',
                        [f'sum by(service)(rate(traefik_service_requests_total{{{ingress}}}[$__rate_interval]))'], 0, y, 8, 8, 'reqps', legends=['{{service}}']))
    p = panel('HTTP response classes', '2xx / 4xx / 5xx request rates for selected services. Missing error classes use zero only when total request telemetry exists.', 'timeseries',
              [http_rate('2..'), http_rate('4..'), http_rate('5..')], 8, y, 8, 8, 'reqps', legends=['2xx · success', '4xx · client error', '5xx · server error'])
    for name, color in [('2xx · success', 'green'), ('4xx · client error', 'yellow'), ('5xx · server error', 'red')]:
        p['fieldConfig']['overrides'].append({'matcher': {'id': 'byName', 'options': name}, 'properties': [{'id': 'color', 'value': {'mode': 'fixed', 'fixedColor': color}}]})
    panels.append(p)
    panels.append(panel('Request latency · p50 / p95 / p99', 'Traefik service histogram quantiles over the rate window, aggregated across selected application services. Low traffic can produce gaps and coarse estimates.', 'timeseries',
                        [latency(0.5), latency(0.95), latency(0.99)], 16, y, 8, 8, 's', legends=['p50', 'p95', 'p99']))
    y += 8
    row('02  /  Delivery & application health')
    panels.append(panel('Available replicas · backend / frontend', 'Observed available replicas by namespace and deployment. Pair with missing replicas; this is not an external HTTP availability probe.', 'bargauge',
                        [available], 0, y, 8, 6, thresholds=[{'color': 'red', 'value': None}, {'color': 'green', 'value': 1}], legends=['{{namespace}} / {{deployment}}'], instant=True))
    panels.append(panel('Missing replicas · backend / frontend', 'Desired minus available, never negative. An absent availability series counts as desired replicas missing. Entirely missing desired series stay absent.', 'bargauge',
                        [missing], 8, y, 8, 6, thresholds=bad_high, legends=['{{namespace}} / {{deployment}}'], instant=True))
    p = panel('Argo CD · sync & health', 'Environment applications only. Health and sync are distinct columns. A missing application is not reported healthy.', 'table',
              [f'max by(name,health_status,sync_status)(argocd_app_info{{{app}}})'], 16, y, 8, 6, instant=True)
    p['transformations'] = [{'id': 'organize', 'options': {'excludeByName': {'Time': True, 'Value': True},
                            'indexByName': {'name': 0, 'health_status': 1, 'sync_status': 2},
                            'renameByName': {'name': 'Application', 'health_status': 'Health', 'sync_status': 'Sync'}}}]
    panels.append(p)
    y += 6
    panels.append(panel('Container restarts · last 15m', 'Recent restart increases grouped by environment/pod. Only counters observed in the selected namespaces contribute.', 'timeseries',
                        [f'sum by(namespace,pod)(increase(kube_pod_container_status_restarts_total{{{selector}}}[15m]))'], 0, y, 12, 7, legends=['{{namespace}} / {{pod}}']))
    panels.append(panel('Pod readiness', 'Readiness gauge by namespace and pod: 1 Ready, 0 not Ready. Succeeded batch jobs are excluded; disappearing pod metrics leave gaps.', 'timeseries',
                        [f'max by(namespace,pod)(kube_pod_status_ready{{{selector},condition="true"}}) unless on(namespace,pod) max by(namespace,pod)(kube_pod_status_phase{{{selector},phase=~"Succeeded|Failed"}} == 1)'],
                        12, y, 12, 7, 'percentunit', legends=['{{namespace}} / {{pod}}']))
    y += 7
    children = row('03  /  DEV ↔ STAGE comparison' if nonprod else '03  /  Production service investigation', collapsed=True)
    if nonprod:
        by_env = lambda expr: f'label_replace({expr},"environment","$1","service","app-(dev|stage)-.*")'
        throughput = f'sum by(environment)({by_env(f"sum by(service)(rate(traefik_service_requests_total{{{ingress}}}[$__rate_interval]))")})'
        error = f'sum by(environment)({by_env(http_rate("5..", "service"))}) / ({throughput} > 0)'
        histogram = f'sum by(le,environment)(label_replace(rate(traefik_service_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval]),"environment","$1","service","app-(dev|stage)-.*"))'
        comparison = [('Environment request rate', throughput, 'reqps'), ('Environment 5xx fraction', error, 'percentunit'),
                      ('Environment p95 latency', f'histogram_quantile(0.95,{histogram})', 's')]
        for i, (title, expr, unit) in enumerate(comparison):
            children.append(panel(title, 'DEV and STAGE remain separate series. Environment selection narrows this comparison. No-data gaps are preserved.', 'timeseries', [expr], i*8, y, 8, 7, unit, legends=['{{environment}}']))
    else:
        children.append(panel('5xx errors by service', 'Server-error requests per second by actual PROD service. Zero is backed by observed total counters.', 'timeseries', [http_rate('5..', 'service')], 0, y, 12, 7, 'reqps', legends=['{{service}}']))
        children.append(panel('p95 latency by service', 'PROD backend and frontend service latency, using actual Traefik service labels. No requests yield undefined quantiles.', 'timeseries', [latency(0.95, 'service')], 12, y, 12, 7, 's', legends=['{{service}}']))
    # Collapsed row children use absolute grid positions; next rows occupy only their headers until expanded.
    children = row('04  /  Capacity, requests & limits · USE', collapsed=True)
    for i, (resource, metric, unit) in enumerate([
            ('cpu', f'rate(container_cpu_usage_seconds_total{{{selector},container!="",container!="POD"}}[$__rate_interval])', 'core'),
            ('memory', f'container_memory_working_set_bytes{{{selector},container!="",container!="POD"}}', 'byte')]):
        usage = f'sum by(namespace)({metric})'
        queries = [f'{usage} / (sum by(namespace)(kube_pod_container_resource_{budget}{{{selector},resource="{resource}",unit="{unit}"}}) > 0)' for budget in ['requests', 'limits']]
        children.append(panel(resource.upper() + ' · usage / declared budgets', 'Namespace usage divided by declared requests or limits. All observed application containers contribute to usage; absent/zero total budgets produce no ratio. Requests may legitimately be exceeded.', 'timeseries', queries, i*12, y, 12, 7, 'percentunit', saturation, ['{{namespace}} / requests', '{{namespace}} / limits']))
    node_name = 'node_uname_info{job="node-exporter"}'
    cpu = f'(1 - avg by(instance)(rate(node_cpu_seconds_total{{job="node-exporter",mode="idle"}}[$__rate_interval]))) * on(instance) group_left(nodename) {node_name}'
    memory = f'(1 - node_memory_MemAvailable_bytes{{job="node-exporter"}} / node_memory_MemTotal_bytes{{job="node-exporter"}}) * on(instance) group_left(nodename) {node_name}'
    fs = 'job="node-exporter",mountpoint="/",fstype!~"tmpfs|overlay|squashfs"'
    storage = f'max by(instance)(1 - node_filesystem_avail_bytes{{{fs}}} / node_filesystem_size_bytes{{{fs}}}) * on(instance) group_left(nodename) {node_name}'
    for i, (title, expr) in enumerate([('Node CPU busy', cpu), ('Node memory used', memory), ('Root filesystem used', storage)]):
        children.append(panel(title, 'Cluster-wide node saturation, independent of the Environment filter. Root-filesystem capacity does not represent every PVC or an off-host backup.', 'timeseries', [expr], i*8, y+7, 8, 7, 'percentunit', saturation, ['{{nodename}}']))
    for i, (title, resource, unit, display_unit) in enumerate([('Allocatable CPU', 'cpu', 'core', 'cores'), ('Allocatable memory', 'memory', 'byte', 'bytes')]):
        children.append(panel(title, 'Cluster-wide schedulable capacity reported by kube-state-metrics, rather than raw host capacity.', 'stat',
                              [f'sum(kube_node_status_allocatable{{resource="{resource}",unit="{unit}"}})'], i*12, y+14, 12, 4, display_unit, [{'color': 'blue', 'value': None}], instant=True))
    children = row('05  /  Incidents & monitoring coverage', collapsed=True)
    for i, severity in enumerate(['critical', 'warning']):
        children.append(panel('Active ' + severity, 'Cluster-wide firing alerts, excluding purpose=test. Zero requires a successful Prometheus self-scrape.', 'stat', [alerts(severity)], i*6, y, 6, 5, thresholds=bad_high, instant=True))
    children.append(panel('Discovered scrape targets healthy', 'Healthy / discovered targets. A removed discovery target is outside this denominator; consult PrometheusTargetMissing and MonitoringMetricsMissing alerts.', 'stat', ['sum(up) / count(up)'], 12, y, 12, 5, 'percentunit', [{'color': 'red', 'value': None}, {'color': 'yellow', 'value': 0.99}, {'color': 'green', 'value': 1}], instant=True))
    p = panel('Firing incidents · cluster scope', 'Actual firing warning/critical alerts with environment, namespace and resource labels. Empty means no matching series; check the counts and telemetry first.', 'table',
              ['ALERTS{alertstate="firing",severity=~"critical|warning",purpose!="test"}'], 0, y+5, 12, 7, instant=True)
    p['transformations'] = [{'id': 'organize', 'options': {'excludeByName': {'Time': True, 'Value': True, '__name__': True, 'alertstate': True}}}]
    children.append(p)
    p = panel('Scrape availability by job', 'Average health of currently discovered endpoints per job. Missing jobs have no row rather than a fabricated healthy state.', 'table', ['avg by(job)(up)'], 12, y+5, 12, 7, 'percentunit', [{'color': 'red', 'value': None}, {'color': 'yellow', 'value': 0.99}, {'color': 'green', 'value': 1}], instant=True)
    p['transformations'] = [{'id': 'organize', 'options': {'excludeByName': {'Time': True}, 'renameByName': {'job': 'Job', 'Value': 'Available'}}}]
    children.append(p)
    children = row('06  /  Database, certificates & assurance gaps', collapsed=True)
    children.append(panel('Database pod readiness · Kubernetes only', 'Readiness of observed liora-db-N pods. This is Kubernetes readiness, not SQL connectivity, replication health, RPO or restore verification. No CNPG/Postgres exporter is scraped.', 'bargauge',
                          [f'max by(namespace,pod)(kube_pod_status_ready{{{selector},pod=~"liora-db-[0-9]+",condition="true"}})'], 0, y, 8, 11, 'percentunit', [{'color': 'red', 'value': None}, {'color': 'green', 'value': 1}], ['{{namespace}} / {{pod}}'], True))
    children.append(panel('K3s certificate lifetime · internal only', 'Minimum remaining lifetime per K3s server via its API metrics endpoint, converted from seconds to days. This is NOT public HTTPS/edge certificate validity. No blackbox/cert-manager certificate exporter was observed.', 'bargauge',
                          ['min by(instance)(k3s_certificate_expiration_seconds{job="apiserver"}) / 86400'], 8, y, 8, 11, 'suffix:days', [{'color': 'red', 'value': None}, {'color': 'yellow', 'value': 7}, {'color': 'green', 'value': 30}], ['{{instance}}'], True))
    children[-1]['fieldConfig']['defaults'].update({'min': 0, 'max': 365, 'decimals': 1})
    next_id += 1
    children.append({'id': next_id, 'type': 'text', 'title': 'Assurance · not instrumented', 'gridPos': {'x': 16, 'y': y, 'w': 8, 'h': 11},
                     'description': 'Explicit monitoring gaps, not healthy/zero status values.',
                     'options': {'mode': 'markdown', 'content': '### Backup: NOT INSTRUMENTED\nNo success, freshness or restore evidence. Snapshot duration is not proof of recoverability.\n\n**Database:** pod readiness only; no SQL/replication metrics.\n\n**Public TLS:** not covered by internal K3s certificates.\n\n**External uptime:** no UptimeRobot metrics.\n\nRunbook: `GRAFANA_OPERATIONS_DASHBOARDS.md`.'}})

    for p in list(panels) + [child for r in panels if r.get('collapsed') for child in r['panels']]:
        if p['title'] in ['Requests by Traefik service', '5xx errors by service', 'p95 latency by service']:
            p['transformations'] = [{'id': 'renameByRegex', 'options': {'regex': 'app-(dev|stage|prod)-(backend|frontend)-80@kubernetes', 'renamePattern': '$1 / $2'}}]
        if p['title'] in ['Available replicas · backend / frontend', 'Missing replicas · backend / frontend', 'Database pod readiness · Kubernetes only']:
            p['transformations'] = [{'id': 'renameByRegex', 'options': {'regex': 'app-(dev|stage|prod) / (.*)', 'renamePattern': '$1 / $2'}}]

    def link(title, uid, suffix=''):
        return {'type': 'link', 'title': title, 'url': '/d/' + uid + suffix, 'icon': 'dashboard',
                'includeVars': False, 'keepTime': True, 'targetBlank': False}

    links = [link('Platform & nodes', 'platform-nodes'), link('Traefik detail', 'ingress-traefik'), link('Argo CD detail', 'gitops-argocd')]
    links += ([link('DEV workloads', 'dev-stage-workloads', '?var-namespace=app-dev'), link('STAGE workloads', 'dev-stage-workloads', '?var-namespace=app-stage')]
              if nonprod else [link('PROD workloads', 'prod-workloads', '?var-namespace=app-prod')])
    variables = []
    if nonprod:
        variables = [{'name': 'environment', 'label': 'Environment', 'type': 'custom', 'query': 'DEV : dev,STAGE : stage',
                      'multi': False, 'includeAll': True, 'allValue': 'dev|stage',
                      'current': {'text': 'All', 'value': '$__all'},
                      'options': [{'text': 'All', 'value': '$__all', 'selected': True}, {'text': 'DEV', 'value': 'dev', 'selected': False}, {'text': 'STAGE', 'value': 'stage', 'selected': False}]}]
    return {'uid': f'liora-{cluster}-operations', 'title': f'Liora / {cluster.upper()} Operations',
            'description': f'{cluster.upper()} RED/USE operations. Environment-scoped service/workload signals; clearly labeled cluster-wide capacity and incidents. Kubernetes database readiness is not SQL health.',
            'schemaVersion': 39, 'version': 1, 'style': 'dark', 'editable': False, 'timezone': 'browser',
            'refresh': '1m', 'time': {'from': 'now-1h', 'to': 'now'}, 'graphTooltip': 1,
            'tags': ['Liora', 'Operations', cluster.upper(), 'RED', 'USE'],
            'links': links, 'templating': {'list': variables}, 'panels': panels,
            'timepicker': {'refresh_intervals': ['1m', '2m', '5m', '15m']}}


def main():
    for cluster in ['nonprod', 'prod']:
        cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'monitoring-operations-dashboard',
              'namespace': 'monitoring', 'labels': {'grafana_dashboard': '1'}},
              'data': {f'liora-{cluster}-operations.json': json.dumps(build(cluster), indent=2) + '\n'}}
        path = ROOT / f'kubernetes/platform/{cluster}/monitoring/operations-dashboard.yaml'
        path.write_text('# Generated by scripts/kubernetes/build-operations-dashboards.py\n' + yaml.dump(cm, Dumper=Dumper, sort_keys=False, width=110))
        print('Generated', path.relative_to(ROOT))


if __name__ == '__main__':
    main()
