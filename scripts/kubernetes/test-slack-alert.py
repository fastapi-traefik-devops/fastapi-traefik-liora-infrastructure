#!/usr/bin/env python3
"""After deployment approval, send a bounded synthetic alert only through the testing route."""
import argparse
import datetime as dt
import ipaddress
import json
import urllib.request
import uuid
from urllib.parse import urlparse

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=['nonprod', 'prod'], required=True)
    parser.add_argument('--url', default='http://127.0.0.1:19093')
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if (parsed.scheme != 'http' or not ipaddress.ip_address(parsed.hostname).is_loopback
            or parsed.username or parsed.password or parsed.path not in ['', '/']
            or parsed.query or parsed.fragment):
        raise SystemExit('Use a loopback kubectl port-forward URL.')
    url = args.url.rstrip('/')
    with urllib.request.urlopen(url + '/api/v2/status', timeout=20) as response:
        config = yaml.safe_load(json.load(response)['config']['original'])
    # Refuse the legacy/default route or any drift that might duplicate test notifications.
    root = config['route']
    branches = root.get('routes', [])
    if len(branches) != 1 or root.get('receiver') != 'discard' or root.get('continue', False):
        raise SystemExit('Unexpected live root route; review effective routing before testing.')
    branch = branches[0]
    test = branch.get('routes', [{}])[0]
    slack = next((r for r in config['receivers'] if r['name'] == 'slack-testing'), {})
    expected_file = f'/etc/alertmanager/secrets/monitoring-slack-{args.cluster}/testing-webhook'
    if (branch.get('matchers') != [f'cluster="{args.cluster}"'] or branch.get('continue', False)
            or test.get('matchers') != ['purpose="test"'] or test.get('receiver') != 'slack-testing'
            or test.get('continue', False) or test.get('routes')
            or len(slack.get('slack_configs', [])) != 1
            # Alertmanager 0.34 adds its receiver name as metadata in the status API.
            or slack.get('labels', {}) not in ({}, {'name': 'slack-testing'})
            or set(slack) - {'name', 'labels', 'slack_configs'}):
        raise SystemExit('Testing route or cluster identity mismatch; no alert sent.')
    destination = slack['slack_configs'][0]
    if (destination.get('channel') != '#liora-alerts-testing'
            or destination.get('api_url_file') != expected_file
            or not destination.get('send_resolved')):
        raise SystemExit('Testing receiver mismatch; no alert sent.')
    input('Confirm this webhook is bound to #liora-alerts-testing in Slack, then press Enter: ')
    now = dt.datetime.now(dt.timezone.utc)
    stamp = lambda value: value.isoformat().replace('+00:00', 'Z')
    test_id = str(uuid.uuid4())
    alert = {'labels': {'alertname': 'LioraSlackNotificationTest', 'cluster': args.cluster,
                        'environment': 'TEST', 'namespace': 'monitoring', 'purpose': 'test',
                        'severity': 'info', 'test_id': test_id},
             'annotations': {'summary': 'Controlled Slack FIRING/RESOLVED verification',
                             'description': 'Synthetic notification; no workload failure.',
                             'action': 'Confirm both messages in #liora-alerts-testing and record the test ID.'},
             'startsAt': stamp(now), 'endsAt': stamp(now + dt.timedelta(minutes=15))}

    def send():
        request = urllib.request.Request(url + '/api/v2/alerts', data=json.dumps([alert]).encode(),
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise ValueError('Unexpected status')
        except Exception:
            raise SystemExit('Alertmanager request failed; inspect this test ID internally. No Slack delivery is established.') from None

    try:
        send()
        print(f'FIRING accepted by Alertmanager; test_id={test_id}. Slack receipt is unverified.')
        input('After observing FIRING in #liora-alerts-testing, press Enter to resolve: ')
    finally:
        alert['endsAt'] = stamp(dt.datetime.now(dt.timezone.utc))
        send()
        print('RESOLVED accepted by Alertmanager; confirm receipt in Slack (allow at least 30 seconds).')


if __name__ == '__main__':
    main()
