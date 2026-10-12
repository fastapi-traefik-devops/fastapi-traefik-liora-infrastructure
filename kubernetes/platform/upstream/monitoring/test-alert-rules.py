#!/usr/bin/env python3
"""Test loaded rules with synthetic samples; never inject alerts or stress workloads.

Requires a loopback Prometheus forward on 19090 and PyYAML.
Uses .tools/promtool (copied from the installed image) and matching local rules.
"""
import json
import re
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import urllib.parse
import yaml

rules = yaml.safe_load((Path(__file__).parent / 'rules/dev-stage.yaml').read_text())['spec']['groups'][0]['rules']
loaded = json.load(urllib.request.urlopen('http://127.0.0.1:19090/api/v1/rules', timeout=20))['data']['groups']
group = next(g for g in loaded if g['name'] == 'dev-stage-platform')
for rule in rules:
    live = next(r for r in group['rules'] if r['name'] == rule['alert'])
    canonical = json.load(urllib.request.urlopen('http://127.0.0.1:19090/api/v1/format_query?' + urllib.parse.urlencode({'query': rule['expr']}), timeout=20))['data']
    assert re.sub(r'\s+', '', live['query']) == re.sub(r'\s+', '', canonical) and live['duration'] == {'5m': 300, '10m': 600, '15m': 900}[rule['for']], rule['alert']
    assert live['annotations'] == rule['annotations'] and live['labels'] == rule['labels'], rule['alert']
    assert live['health'] == 'ok' and not live.get('lastError'), rule['alert']

def sample(metric, labels, values):
    return {'series': metric + '{' + ','.join(f'{k}="{v}"' for k, v in labels.items()) + '}', 'values': values}

cases = {
    'NodeMemoryPressure': ([sample('kube_node_status_condition', {'node': 'test', 'condition': 'MemoryPressure', 'status': 'true'}, '1+0x24 0+0x25')], {'node': 'test', 'condition': 'MemoryPressure', 'status': 'true'}, 5),
    'NodeDiskPressure': ([sample('kube_node_status_condition', {'node': 'test', 'condition': 'DiskPressure', 'status': 'true'}, '1+0x24 0+0x25')], {'node': 'test', 'condition': 'DiskPressure', 'status': 'true'}, 5),
    'NodeHighCPU': ([sample('node_cpu_seconds_total', {'instance': 'test', 'mode': 'idle'}, '0+5x24 180+60x25')], {'instance': 'test'}, 16),
    'NodeHighMemory': ([sample('node_memory_MemAvailable_bytes', {'instance': 'test'}, '5+0x24 50+0x25'), sample('node_memory_MemTotal_bytes', {'instance': 'test'}, '100+0x50')], {'instance': 'test'}, 15),
    'ApplicationRestartSpike': ([sample('kube_pod_container_status_restarts_total', {'namespace': 'app-dev', 'pod': 'test', 'container': 'backend'}, '0 3+0x49')], {'namespace': 'app-dev', 'pod': 'test', 'container': 'backend'}, 6),
    'ApplicationDeploymentUnavailable': ([sample('kube_deployment_status_replicas_available', {'namespace': 'app-stage', 'deployment': 'backend'}, '0+0x24 1+0x25'), sample('kube_deployment_spec_replicas', {'namespace': 'app-stage', 'deployment': 'backend'}, '1+0x50')], {'namespace': 'app-stage', 'deployment': 'backend'}, 10),
    'ArgoApplicationUnhealthy': ([sample('argocd_app_info', {'name': 'app-dev', 'health_status': 'Degraded', 'sync_status': 'Synced'}, '1+0x24 0+0x25')], {'name': 'app-dev', 'health_status': 'Degraded', 'sync_status': 'Synced'}, 10),
    'ArgoApplicationOutOfSync': ([sample('argocd_app_info', {'name': 'app-stage', 'health_status': 'Healthy', 'sync_status': 'OutOfSync'}, '1+0x24 0+0x25')], {'name': 'app-stage', 'health_status': 'Healthy', 'sync_status': 'OutOfSync'}, 10),
}
tests = []
for rule in rules:
    samples, labels, fires = cases[rule['alert']]
    tests.append({'name': rule['alert'] + ' pending/firing/recovered', 'interval': '1m', 'input_series': samples, 'alert_rule_test': [
        {'eval_time': f'{fires-1}m', 'alertname': rule['alert'], 'exp_alerts': []},
        {'eval_time': f'{fires}m', 'alertname': rule['alert'], 'exp_alerts': [{'exp_labels': {**labels, **rule['labels']}, 'exp_annotations': rule['annotations']}]},
        {'eval_time': '45m', 'alertname': rule['alert'], 'exp_alerts': []},
    ]})
# Threshold boundaries are healthy: CPU=85%, memory=90%, restarts<3,
# equal available/desired, normal node conditions and Healthy/Synced apps.
healthy = [sample('node_cpu_seconds_total', {'instance': 'test', 'mode': 'idle'}, '0+9x50'), sample('node_memory_MemAvailable_bytes', {'instance': 'test'}, '10+0x50'), sample('node_memory_MemTotal_bytes', {'instance': 'test'}, '100+0x50')]
for condition in ['MemoryPressure', 'DiskPressure']:
    healthy.append(sample('kube_node_status_condition', {'node': 'test', 'condition': condition, 'status': 'true'}, '0+0x50'))
for ns in ['app-dev', 'app-stage']:
    healthy.extend([sample('kube_pod_container_status_restarts_total', {'namespace': ns, 'pod': 'test', 'container': 'backend'}, '0 2+0x49'), sample('kube_deployment_status_replicas_available', {'namespace': ns, 'deployment': 'backend'}, '1+0x50'), sample('kube_deployment_spec_replicas', {'namespace': ns, 'deployment': 'backend'}, '1+0x50'), sample('argocd_app_info', {'name': ns, 'health_status': 'Healthy', 'sync_status': 'Synced'}, '1+0x50')])
# Unhealthy synthetic PROD samples must never match application rules.
healthy.extend([sample('kube_pod_container_status_restarts_total', {'namespace': 'app-prod', 'pod': 'test', 'container': 'backend'}, '0+10x50'), sample('kube_deployment_status_replicas_available', {'namespace': 'app-prod', 'deployment': 'backend'}, '0+0x50'), sample('kube_deployment_spec_replicas', {'namespace': 'app-prod', 'deployment': 'backend'}, '1+0x50'), sample('argocd_app_info', {'name': 'app-prod', 'health_status': 'Degraded', 'sync_status': 'OutOfSync'}, '1+0x50')])
tests.append({'name': 'Healthy boundaries and environment isolation', 'interval': '1m', 'input_series': healthy, 'alert_rule_test': [{'eval_time': t, 'alertname': r['alert'], 'exp_alerts': []} for r in rules for t in ['6m', '30m']]})
with tempfile.TemporaryDirectory(prefix='monitoring-alert-tests-') as directory:
    rulefile = Path(directory) / 'rules.yaml'
    rulefile.write_text(yaml.safe_dump({'groups': [{'name': 'dev-stage-platform', 'rules': rules}]}))
    testfile = Path(directory) / 'tests.yaml'
    testfile.write_text(yaml.safe_dump({'rule_files': [str(rulefile)], 'evaluation_interval': '1m', 'tests': tests}))
    promtool = Path(__file__).resolve().parent.parent / '.tools/promtool'
    subprocess.run([str(promtool), 'test', 'rules', str(testfile)], check=True)
print('Eight live rules match local definitions; pending/firing/recovery and healthy boundary/isolation tests PASS')
