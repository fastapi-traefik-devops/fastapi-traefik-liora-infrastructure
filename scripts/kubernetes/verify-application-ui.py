#!/usr/bin/env python3
"""Check private ingress, UI login and item persistence without logging credentials."""

import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
import uuid

from playwright.sync_api import expect, sync_playwright
import yaml


def main():
    environment = os.environ['environment']
    hosts = {
        'dev': 'dev.liora.aprt.info',
        'stage': 'stage.liora.aprt.info',
        'prod': 'liora.aprt.info',
    }
    hostname = hosts[environment]
    url = os.environ.get('acceptance_url', f'http://{hostname}:18080').rstrip('/')
    parsed = urlparse(url)
    assert parsed.hostname == hostname and parsed.scheme in ['http', 'https']
    assert parsed.username is None and parsed.password is None
    assert not parsed.query and not parsed.fragment and parsed.path in ['', '/']
    assert os.environ['namespace'] == 'app-' + environment
    recovery = Path(os.environ['recovery_dir']) / 'recovery.yaml'
    entry = yaml.safe_load(recovery.read_text())['application_credentials'][environment]
    assert entry['namespace'] == os.environ['namespace']
    password = entry['backend-secrets']['FIRST_SUPERUSER_PASSWORD']
    assert 8 <= len(password) <= 40
    result = {'environment': environment, 'namespace': entry['namespace'],
              'url': url, 'verified': False, 'step': 'launch browser'}
    record = Path(os.environ['render_dir']) / 'acceptance.json'
    title = f'acceptance-{environment}-{uuid.uuid4().hex[:12]}'
    record.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                '--no-proxy-server',
                f'--host-resolver-rules=MAP {hostname} 127.0.0.1',
            ])
            page = browser.new_page()
            page.set_default_timeout(60000)
            result['step'] = 'backend health through ingress'
            response = page.goto(url + '/api/v1/utils/health-check/')
            assert response.status == 200
            expect(page.locator('body')).to_have_text('true')
            result['step'] = 'UI login'
            response = page.goto(url + '/login')
            assert response.status == 200
            page.get_by_placeholder('Email', exact=True).fill(entry['first_superuser'])
            page.get_by_placeholder('Password', exact=True).fill(password)
            with page.expect_response(lambda r: urlparse(r.url).path == '/api/v1/login/access-token'
                                      and r.request.method == 'POST') as login:
                page.get_by_role('button', name='Log In', exact=True).click()
            assert login.value.status == 200
            page.wait_for_url(url + '/')
            expect(page.get_by_text('Welcome back, nice to see you again!')).to_be_visible()
            result['step'] = 'create item through UI'
            page.goto(url + '/items')
            expect(page.get_by_role('heading', name='Items Management')).to_be_visible()
            page.get_by_role('button', name='Add Item', exact=True).click()
            page.get_by_placeholder('Title', exact=True).fill(title)
            page.get_by_placeholder('Description', exact=True).fill('Private deployment acceptance marker')
            with page.expect_response(lambda r: urlparse(r.url).path == '/api/v1/items/'
                                      and r.request.method == 'POST') as created:
                page.get_by_role('button', name='Save', exact=True).click()
            assert created.value.status in [200, 201]
            result['item_id'] = created.value.json()['id']
            result['title'] = title
            row = page.get_by_role('row').filter(has_text=title)
            expect(row).to_be_visible()
            result['step'] = 'update item through UI'
            row.get_by_role('button').click()
            page.get_by_role('button', name='Edit Item', exact=True).click()
            updated_title = title + '-updated'
            page.get_by_placeholder('Title', exact=True).fill(updated_title)
            with page.expect_response(lambda r: urlparse(r.url).path == '/api/v1/items/' + result['item_id']
                                      and r.request.method == 'PUT') as updated:
                page.get_by_role('button', name='Save', exact=True).click()
            assert updated.value.status == 200
            result['title'] = updated_title
            result['step'] = 'read persisted item after browser reload'
            page.reload()
            expect(page.get_by_role('row').filter(has_text=updated_title)).to_be_visible()
            persisted = page.evaluate('''async id => {
                const response = await fetch('/api/v1/items/' + id, {
                    headers: {Authorization: 'Bearer ' + localStorage.getItem('access_token')}
                });
                return {status: response.status, item: await response.json()};
            }''', result['item_id'])
            assert persisted['status'] == 200 and persisted['item']['title'] == updated_title
            result.update(verified=True, step='complete', marker_retained_for_isolation=True)
            browser.close()
    except Exception as error:
        result['error_type'] = type(error).__name__
        # Playwright error details and traces can contain filled password values.
        record.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), file=sys.stderr)
        return 1
    record.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
    except Exception as error:
        # Recovery parsing failures must not echo lines containing credential values.
        print(json.dumps({'verified': False, 'step': 'setup',
                          'error_type': type(error).__name__}), file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)
