#!/usr/bin/env python3
"""Validate routing, message templates, rules and pinned Helm rendering without cluster access."""
import argparse
import base64
import hashlib
import itertools
import io
import json
from pathlib import Path
import subprocess
import runpy
import sys
import tempfile
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]


def run(command):
    result = subprocess.run([str(p) for p in command], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['amtool', 'promtool', 'helm', 'chart']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    chart = Path(args.chart).resolve()
    lock = json.loads((ROOT / 'kubernetes/platform/chart-lock.json').read_text())
    assert hashlib.sha256(chart.read_bytes()).hexdigest() == lock['sha256'], 'Chart checksum mismatch'
    with tempfile.TemporaryDirectory(prefix='liora-slack-') as tmp:
        work = Path(tmp)
        for cluster in ['nonprod', 'prod']:
            directory = ROOT / f'kubernetes/platform/{cluster}/monitoring'
            values = yaml.safe_load((directory / 'values.yaml').read_text())
            config = values['alertmanager']['config']
            config_file = work / f'{cluster}-alertmanager.yaml'
            config_file.write_text(yaml.safe_dump(config))
            run([args.amtool, 'check-config', config_file])
            # Exercise the actual helper against raw and API-normalized receiver metadata.
            # Stop at its first prompt, before any alert can be submitted.
            for receiver_labels in [None, {'name': 'slack-testing'}, {'name': 'wrong'}]:
                fixture_config = yaml.safe_load(yaml.safe_dump(config))
                test_receiver = next(r for r in fixture_config['receivers'] if r['name'] == 'slack-testing')
                if receiver_labels is not None:
                    test_receiver['labels'] = receiver_labels
                response = json.dumps({'config': {'original': yaml.safe_dump(fixture_config)}}).encode()
                with mock.patch.object(sys, 'argv', ['test-slack-alert.py', '--cluster', cluster]), \
                     mock.patch('urllib.request.urlopen', return_value=io.BytesIO(response)) as request, \
                     mock.patch('builtins.input', side_effect=RuntimeError('preflight reached prompt')) as prompt:
                    try:
                        runpy.run_path(str(ROOT / 'scripts/kubernetes/test-slack-alert.py'), run_name='__main__')
                    except RuntimeError as exc:
                        assert str(exc) == 'preflight reached prompt' and receiver_labels != {'name': 'wrong'}
                    except SystemExit:
                        assert receiver_labels == {'name': 'wrong'}
                    else:
                        raise AssertionError('Expected helper to stop before sending')
                    assert request.call_count == 1, 'Helper must not send alerts during preflight validation'
                    assert prompt.call_count == (0 if receiver_labels == {'name': 'wrong'} else 1)
            # Every combination must produce exactly one destination, including test criticals.
            identities = [cluster, 'prod' if cluster == 'nonprod' else 'nonprod', 'wrong', '']
            for identity, purpose, severity in itertools.product(identities, ['', 'test', 'synthetic'], ['info', 'warning', 'critical']):
                receiver = ('discard' if identity != cluster else
                            'slack-testing' if purpose == 'test' else 'slack-' + cluster)
                run([args.amtool, 'config', 'routes', 'test', '--config.file=' + str(config_file),
                     '--verify.receivers=' + receiver, 'cluster=' + identity,
                     'purpose=' + purpose, 'severity=' + severity, 'alertname=Example'])
            assert values['alertmanager']['alertmanagerSpec']['secrets'] == ['monitoring-slack-' + cluster]
            for receiver in config['receivers'][1:]:
                slack = receiver['slack_configs'][0]
                assert slack['send_resolved'] and 'api_url' not in slack
                expected_channel = '#liora-alerts-testing' if receiver['name'] == 'slack-testing' else '#liora-alerts-' + cluster
                assert slack['channel'] == expected_channel
                template = work / 'message.tmpl'
                template.write_text('{{ define "title" }}' + slack['title'] + '{{ end }}\n'
                                    '{{ define "text" }}' + slack['text'] + '{{ end }}')
                alerts = []
                for namespace, status in [('app-dev', 'firing'), ('app-stage', 'resolved'), ('app-prod', 'resolved'), ('monitoring', 'firing')]:
                    alerts.append({'status': status, 'labels': {'alertname': 'Example', 'namespace': namespace,
                                   'severity': 'warning', 'deployment': 'backend', 'cluster': cluster},
                                   'annotations': {'description': 'Example description', 'action': 'Inspect deployment'},
                                   'startsAt': '2026-10-23T10:00:00Z',
                                   'endsAt': '2026-10-23T10:05:00Z' if status == 'resolved' else '0001-01-01T00:00:00Z'})
                data = work / 'alerts.json'
                data.write_text(json.dumps({'status': 'firing', 'alerts': alerts,
                                            'commonLabels': {'alertname': 'Example', 'severity': 'warning'}}))
                output = run([args.amtool, 'template', 'render', '--template.glob=' + str(template),
                              '--template.data=' + str(data), '--template.text={{ template "title" . }} {{ template "text" . }}'])
                for fragment in [f'*Cluster:* {cluster.upper()}', '*Environment:* DEV', '*Environment:* STAGE',
                                 '*Environment:* PROD', '*Environment:* PLATFORM', '*Severity:* warning',
                                 '*Deployment:* backend', '*Description:* Example description', '*Action:* Inspect deployment',
                                 '*Started:* 2026-10-23 10:00:00 UTC', '*Resolved:* 2026-10-23 10:05:00 UTC']:
                    assert fragment in output, (cluster, fragment, output)
                assert '0001' not in output and '<no value>' not in output
                data.write_text(json.dumps({'status': 'resolved', 'alerts': [alerts[1]],
                                            'commonLabels': {'alertname': 'Example'}}))
                output = run([args.amtool, 'template', 'render', '--template.glob=' + str(template),
                              '--template.data=' + str(data), '--template.text={{ template "title" . }}'])
                assert '[RESOLVED]' in output
            rule_doc = yaml.safe_load((directory / 'rules.yaml').read_text())
            rule_file = work / f'{cluster}-rules.yaml'
            rule_file.write_text(yaml.safe_dump({'groups': rule_doc['spec']['groups']}))
            run([args.promtool, 'check', 'rules', rule_file])
            fixtures = yaml.safe_load((ROOT / 'scripts/kubernetes/tests/slack-rules.yaml').read_text())
            fixtures['rule_files'] = [str(rule_file)]
            if cluster == 'nonprod':
                fixtures['tests'] = [t for t in fixtures['tests'] if not t.get('name', '').startswith('prod:')]
            # Assert expressions using promql_expr_test, independent of cluster-specific annotations.
            selected = {r['alert']: r['expr'] for g in rule_doc['spec']['groups'] for r in g['rules']}
            for test in fixtures['tests']:
                for case in test.get('promql_expr_test', []):
                    case['expr'] = selected[case['expr']]
            fixture_file = work / 'rule-tests.yaml'
            fixture_file.write_text(yaml.safe_dump(fixtures))
            run([args.promtool, 'test', 'rules', fixture_file])
            rendered = run([args.helm, 'template', 'monitoring', chart, '--namespace', 'monitoring',
                            '--values', directory / 'values.yaml'])
            manifests = list(yaml.safe_load_all(rendered))
            secret = next(m for m in manifests if m and m['kind'] == 'Secret' and m['metadata']['name'] == 'alertmanager-monitoring-alertmanager')
            actual = yaml.safe_load(base64.b64decode(secret['data']['alertmanager.yaml']))
            assert actual == config, 'Helm altered Alertmanager configuration'
            am = next(m for m in manifests if m and m['kind'] == 'Alertmanager')
            assert am['spec']['secrets'] == ['monitoring-slack-' + cluster]
            print(f'{cluster}: PASS config, 36 routing cases, FIRING/RESOLVED templates, rule syntax/behavior, Helm render/Secret mount')


if __name__ == '__main__':
    main()
