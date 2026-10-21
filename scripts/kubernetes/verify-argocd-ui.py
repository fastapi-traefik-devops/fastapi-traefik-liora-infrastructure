#!/usr/bin/env python3
"""Verify private Argo CD UI login without logging or saving credentials."""

import base64
import json
import os
import subprocess
import sys

from playwright.sync_api import expect, sync_playwright


def main():
    cluster = os.environ['argocd_cluster']
    assert cluster in ('nonprod', 'prod')
    kubeconfig = os.environ['kubeconfig']
    expected = '/home/root-admin/.kube/config-' + ('prod' if cluster == 'prod' else 'dev-stage')
    assert kubeconfig == expected
    port = int(os.environ.get('argocd_port', '18443' if cluster == 'nonprod' else '19443'))
    assert 1024 <= port <= 65535
    result = subprocess.run(
        ['kubectl', '--kubeconfig=' + kubeconfig, '-n', 'argocd', 'get',
         'secret', 'argocd-initial-admin-secret', '-o', 'json'],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    password = base64.b64decode(json.loads(result.stdout)['data']['password']).decode()
    assert password
    url = f'https://127.0.0.1:{port}'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-proxy-server'])
        # Only the fixed localhost Service forward uses the bootstrap certificate.
        page = browser.new_page(ignore_https_errors=True)
        page.set_default_timeout(180000)
        response = page.goto(url + '/login', timeout=180000)
        assert response.status == 200
        page.locator('input[name="username"]').fill('admin')
        page.locator('input[name="password"]').fill(password)
        page.get_by_role('button', name='Sign In', exact=True).click()
        page.wait_for_url('**/applications*', timeout=180000)
        expect(page.get_by_text('Applications', exact=True).first).to_be_visible()
        info = page.evaluate('''async () => {
            const response = await fetch('/api/v1/session/userinfo');
            const body = await response.json();
            return {status: response.status, loggedIn: body.loggedIn, username: body.username};
        }''')
        assert info == {'status': 200, 'loggedIn': True, 'username': 'admin'}
        browser.close()
    print(json.dumps({'cluster': cluster, 'private_ui_login': True,
                      'authenticated_api': True, 'credentials_saved': False}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Browser errors can include input values: print only the exception type.
        print(json.dumps({'verified': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
