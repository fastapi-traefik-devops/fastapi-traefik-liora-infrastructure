#!/usr/bin/env python3
"""Send a bounded test alert to loopback Alertmanager and resolve the same labels."""
import datetime
import json
import urllib.request
import uuid

def timestamp(value):
    return value.isoformat().replace('+00:00', 'Z')

now = datetime.datetime.now(datetime.timezone.utc)
test_id = str(uuid.uuid4())
alert = {
    'labels': {'alertname': 'AlertmanagerNotificationTest', 'severity': 'info',
               'namespace': 'monitoring', 'test_id': test_id},
    'annotations': {'summary': 'Controlled Slack delivery test ' + test_id},
    'startsAt': timestamp(now),
    'endsAt': timestamp(now + datetime.timedelta(minutes=15)),
}

def send():
    req = urllib.request.Request('http://127.0.0.1:19093/api/v2/alerts',
                                 data=json.dumps([alert]).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            assert response.status == 200
    except Exception:
        raise SystemExit('Alertmanager request failed; inspect the test alert internally.') from None

try:
    send()
    print('FIRING accepted by Alertmanager; test_id=' + test_id, flush=True)
    input('After confirming FIRING in Slack, press Enter to resolve (15-minute fallback expiry): ')
finally:
    alert['endsAt'] = timestamp(datetime.datetime.now(datetime.timezone.utc))
    send()
    print('RESOLVED accepted by Alertmanager for the same test_id; confirm receipt in Slack.')
