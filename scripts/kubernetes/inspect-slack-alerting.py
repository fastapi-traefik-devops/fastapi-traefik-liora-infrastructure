#!/usr/bin/env python3
"""Read monitoring status without printing webhook credentials or raw configuration."""
import argparse
import json
from pathlib import Path
import urllib.request

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=['nonprod', 'prod'], required=True)
    parser.add_argument('--expect-slack', action='store_true', help='Require the repository routing, templates and rules to be loaded')
    args = parser.parse_args()
    vip = {'nonprod': '192.168.77.16', 'prod': '192.168.77.17'}[args.cluster]

    def api(port, path):
        with urllib.request.urlopen(f'http://{vip}:{port}{path}', timeout=20) as response:
            return json.load(response)

    status = api(9093, '/api/v2/status')
    live = yaml.safe_load(status['config']['original'])
    print(f'Cluster: {args.cluster}; Alertmanager: {status["versionInfo"]["version"]}')

    def route_summary(route):
        # Expose only routing metadata; never serialize the complete config.
        keys = ['receiver', 'matchers', 'group_by', 'group_wait', 'group_interval', 'repeat_interval', 'continue']
        return {**{k: route[k] for k in keys if k in route},
                'routes': [route_summary(r) for r in route.get('routes', [])]}

    print('Routing:', json.dumps(route_summary(live['route'])))
    for receiver in live['receivers']:
        print('Receiver:', receiver['name'], json.dumps([
            {k: s.get(k) for k in ['channel', 'api_url_file', 'send_resolved']}
            for s in receiver.get('slack_configs', [])]))
    groups = api(9090, '/api/v1/rules')['data']['groups']
    rules = [r for g in groups for r in g['rules'] if r.get('type') == 'alerting']
    print('Loaded alerts:', json.dumps([{'name': r['name'], 'health': r.get('health'),
                                       'state': r.get('state'), 'severity': r.get('labels', {}).get('severity')}
                                      for r in rules]))
    if args.expect_slack:
        root = Path(__file__).resolve().parents[2]
        folder = root / f'kubernetes/platform/{args.cluster}/monitoring'
        expected = yaml.safe_load((folder / 'values.yaml').read_text())['alertmanager']['config']

        def normalized(route):
            route = dict(route)
            if not route.get('continue'):
                route.pop('continue', None)
            route['routes'] = [normalized(r) for r in route.get('routes', [])]
            return route

        assert normalized(live['route']) == normalized(expected['route']), 'Live routing differs from Git'
        by_name = {r['name']: r for r in live['receivers']}
        assert set(by_name) == {r['name'] for r in expected['receivers']}, 'Live receivers differ from Git'
        for receiver in expected['receivers']:
            actual = by_name[receiver['name']].get('slack_configs', [])
            wanted = receiver.get('slack_configs', [])
            assert len(actual) == len(wanted), 'Slack receiver count differs'
            for configured, target in zip(actual, wanted):
                for key in ['channel', 'api_url_file', 'send_resolved', 'title', 'text']:
                    assert configured.get(key) == target.get(key), f'Receiver {receiver["name"]}: {key} differs'
        wanted_rules = yaml.safe_load((folder / 'rules.yaml').read_text())['spec']['groups'][0]['rules']
        loaded = {r['name']: r for r in rules}
        for rule in wanted_rules:
            assert rule['alert'] in loaded, f'Missing rule: {rule["alert"]}'
            actual = loaded[rule['alert']]
            assert actual['health'] == 'ok', f'Unhealthy rule: {rule["alert"]}'
            assert actual['labels'] == rule['labels'], f'Labels differ: {rule["alert"]}'
        print('PASS: expected routing, receiver templates and healthy alert inventory loaded.')
    print('Slack message receipt is not established by these checks.')


if __name__ == '__main__':
    main()
