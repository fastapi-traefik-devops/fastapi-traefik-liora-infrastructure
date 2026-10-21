#!/usr/bin/env python3
"""Render an Argo Helm bootstrap while monitoring Git files remain unpublished.

Requires PyYAML. Writes only a credential-free Application to stdout.
After the reviewed Git merge, apply argocd/app-monitoring.yaml instead.
This is an operator bootstrap helper, not a CI pipeline or Helm installer.
"""
import copy
from pathlib import Path
import yaml

root = Path(__file__).resolve().parent.parent

def load(relative):
    return yaml.safe_load((root / relative).read_text())

app = load('argocd/app-monitoring.yaml')
values = load('monitoring/values.yaml')
values['prometheus']['additionalServiceMonitors'] = [
    {'name': item['metadata']['name'], **item['spec']}
    for item in yaml.safe_load_all((root / 'monitoring/monitors/argocd.yaml').read_text())
]
monitor = load('monitoring/monitors/traefik.yaml')
values['prometheus']['additionalPodMonitors'] = [
    {'name': monitor['metadata']['name'], **monitor['spec']}
]
rule = load('monitoring/rules/dev-stage.yaml')
values['additionalPrometheusRulesMap'] = {rule['metadata']['name']: rule['spec']}
dashboard = load('monitoring/dashboards/platform.yaml')
values['grafana']['dashboards'] = {
    'default': {
        name.removesuffix('.json'): {'json': contents}
        for name, contents in dashboard['data'].items()
    }
}
values['grafana']['dashboardProviders'] = {
    'dashboardproviders.yaml': {
        'apiVersion': 1,
        'providers': [{
            'name': 'bootstrap', 'orgId': 1, 'folder': 'DEV-STAGE',
            'type': 'file', 'disableDeletion': True, 'editable': False,
            'options': {'path': '/var/lib/grafana/dashboards/default'},
        }],
    }
}
source = copy.deepcopy(app['spec'].pop('sources')[0])
source['helm'].pop('valueFiles')
source['helm']['valuesObject'] = values
app['spec']['source'] = source
# A fresh bootstrap always pauses; activation requires the explicit capacity phase.
app['metadata'].setdefault('annotations', {})['argocd.argoproj.io/skip-reconcile'] = 'true'
app['spec']['syncPolicy']['automated']['enabled'] = False
print(yaml.safe_dump(app, sort_keys=False), end='')
