#!/usr/bin/env python3
"""Render Slack templates with matching-version amtool; no cluster or credentials.

Usage: python3 monitoring/test-slack-format.py --amtool /path/to/amtool
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--amtool', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
values = yaml.safe_load((root / 'values.yaml').read_text())
slack = values['alertmanager']['config']['receivers'][0]['slack_configs'][0]
assert slack['send_resolved'] is True
assert slack['api_url_file'] == '/etc/alertmanager/secrets/monitoring-slack-webhook/slack-webhook'

with tempfile.TemporaryDirectory(prefix='slack-format-') as tmp:
    directory = Path(tmp)
    template = directory / 'slack.tmpl'
    template.write_text('{{ define "test.title" }}' + slack['title'] + '{{ end }}\n'
                        '{{ define "test.text" }}' + slack['text'] + '{{ end }}')
    def render(alerts, status='firing', common=None, part='text'):
        data = {'status': status, 'alerts': alerts, 'commonLabels': common or {},
                'commonAnnotations': {}, 'groupLabels': {}}
        fixture = directory / 'alerts.json'
        fixture.write_text(json.dumps(data))
        return subprocess.check_output([args.amtool, 'template', 'render',
            '--template.glob=' + str(template), '--template.data=' + str(fixture),
            '--template.text={{ template "test.' + part + '" . }}'], text=True)

    def alert(labels=None, annotations=None, status='firing'):
        return {'status': status, 'labels': {'alertname': 'ExampleAlert', **(labels or {})},
                'annotations': annotations or {}, 'startsAt': '2026-10-17T12:00:00Z',
                'endsAt': '2026-10-17T12:10:00Z' if status == 'resolved' else '0001-01-01T00:00:00Z'}

    full = alert({'severity': 'warning', 'namespace': 'app-stage', 'pod': 'backend-1',
                  'node': 'worker-1', 'deployment': 'backend', 'service': 'api',
                  'instance': '10.0.0.1:8080', 'container': 'backend'},
                 {'summary': 'Replicas unavailable', 'description': 'One replica is unavailable'})
    text = render([full])
    for expected in ['[FIRING] ExampleAlert', '*Severity:* warning\n', '*Environment:* STAGE\n',
                     '*Namespace:* app-stage\n', '*Pod:* backend-1\n', '*Node:* worker-1\n',
                     '*Deployment:* backend\n', '*Service:* api\n', '*Instance:* 10.0.0.1:8080\n',
                     '*Container:* backend\n', '*Summary:* Replicas unavailable\n',
                     '*Description:* One replica is unavailable\n', '*Started:* 2026-10-17 12:00:00 UTC']:
        assert expected in text, (expected, text)
    assert '*Resolved:*' not in text
    sparse = render([alert()])
    assert '<no value>' not in sparse and '0001' not in sparse
    for absent in ['Severity:', 'Environment:', 'Namespace:', 'Pod:', 'Description:', 'http']:
        assert absent not in sparse, sparse
    for scope, expected in [('app-dev', 'DEV'), ('app-stage', 'STAGE'), ('app-prod', 'PROD')]:
        for label in ['namespace', 'name']:
            assert '*Environment:* ' + expected in render([alert({label: scope})])
    assert '*Environment:*' not in render([alert({'namespace': 'monitoring'})])
    assert '*Environment:* DEV' in render([alert({'namespace': 'argocd', 'name': 'app-dev'})])
    assert '*Environment:* PROD' in render([alert({'environment': 'prod', 'namespace': 'app-dev'})])
    assert '*Environment:* DEV' in render([alert({'env': 'dev'})])
    recovered = alert({'severity': 'critical', 'namespace': 'app-prod', 'pod': 'backend-2'}, status='resolved')
    text = render([full, recovered], common={'severity': 'info', 'pod': 'wrong-common-value'})
    first, second = text.split('*[RESOLVED]')
    assert '*Severity:* warning' in first and '*Pod:* backend-1' in first and '*Resolved:*' not in first
    assert '*Severity:* critical' in second and '*Pod:* backend-2' in second
    assert '*Resolved:* 2026-10-17 12:10:00 UTC' in second
    assert 'wrong-common-value' not in text and '*Severity:* info' not in text
    assert '[RESOLVED] ExampleAlert' in render([recovered], status='resolved', common={'alertname': 'ExampleAlert'}, part='title')
print('Slack template tests PASS: optional fields, DEV/STAGE/PROD, explicit environment, mixed grouped alerts, UTC firing/resolution times')
