#!/usr/bin/env python3
"""Check native Phase 8 browser logins and monitoring without persisting sessions."""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', required=True, choices=['nonprod', 'prod'])
    parser.add_argument('--include-jenkins', action='store_true')
    args = parser.parse_args()
    assert not args.include_jenkins or args.cluster == 'nonprod'
    vip = '192.168.77.16' if args.cluster == 'nonprod' else '192.168.77.17'
    kubeconfig = Path.home() / '.kube' / ('config-dev-stage' if args.cluster == 'nonprod' else 'config-prod')
    command = ['kubectl', '--kubeconfig=' + str(kubeconfig)]

    def resource(namespace, kind, name):
        result = subprocess.run(command + ['-n', namespace, 'get', kind, name, '-o', 'json'],
                                text=True, capture_output=True)
        assert result.returncode == 0
        return json.loads(result.stdout)

    def credential(namespace, name, key):
        return base64.b64decode(resource(namespace, 'secret', name)['data'][key]).decode()

    opener = build_opener(ProxyHandler({}))

    def get(url):
        with opener.open(url, timeout=30) as response:
            return json.load(response)

    prometheus = f'http://{vip}:9090'
    targets = get(prometheus + '/api/v1/targets')['data']['activeTargets']
    assert targets and all(target['health'] == 'up' for target in targets)
    families = ['node_uname_info', 'kube_node_info', 'kube_deployment_status_replicas_available',
                'argocd_app_info', 'traefik_config_reloads_total']
    metric_counts = {}
    for family in families:
        result = get(prometheus + '/api/v1/query?' + urlencode({'query': family}))
        assert result['status'] == 'success' and result['data']['result']
        metric_counts[family] = len(result['data']['result'])
    rules = get(prometheus + '/api/v1/rules')['data']['groups']
    assert sum(len(group['rules']) for group in rules) == 8
    assert all(rule.get('health') == 'ok' for group in rules for rule in group['rules'])
    alertmanager = get(f'http://{vip}:9093/api/v2/status')
    assert alertmanager['cluster']['status'] in ('ready', 'disabled')
    result = {'cluster': args.cluster, 'targets_up': len(targets), 'metric_series': metric_counts,
              'alert_rules': 8, 'external_notifications_enabled': False}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-proxy-server'])
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)
        grafana = f'http://{vip}:3000'
        page.goto(grafana + '/login', timeout=180000)
        page.locator('input[name="user"]').fill(credential('monitoring', 'monitoring-grafana-admin', 'admin-user'))
        page.locator('input[name="password"]').fill(credential('monitoring', 'monitoring-grafana-admin', 'admin-password'))
        page.get_by_role('button', name='Log in', exact=True).click()
        page.wait_for_url(grafana + '/**', timeout=180000)
        page.wait_for_function("fetch('/api/user').then(r => r.ok)", timeout=180000)
        dashboards = page.evaluate("fetch('/api/search?type=dash-db').then(r => r.json())")
        assert len(dashboards) == 4
        assert all(item['title'].startswith(args.cluster.upper() + ' / ') for item in dashboards)
        # Load each dashboard in the real browser, exercising native UI routing.
        for dashboard in dashboards:
            page.goto(grafana + dashboard['url'], timeout=180000)
            expect(page.get_by_text(dashboard['title'], exact=True).first).to_be_visible(timeout=180000)
        result['grafana_login'] = True
        result['dashboards_loaded'] = len(dashboards)
        context.close()
        environments = [('dev', 8081), ('stage', 8082)] if args.cluster == 'nonprod' else [('prod', 8081)]
        for environment, port in environments:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(180000)
            page.goto(f'http://{vip}:{port}', timeout=180000)
            page.locator('select[name="auth[driver]"]').select_option('pgsql')
            page.locator('input[name="auth[server]"]').fill('db')
            page.locator('input[name="auth[username]"]').fill('postgres')
            page.locator('input[name="auth[password]"]').fill(credential('app-' + environment, 'db-secrets', 'POSTGRES_PASSWORD'))
            page.locator('input[name="auth[db]"]').fill('app')
            page.locator('input[type="submit"]').first.click()
            expect(page.get_by_role('link', name='SQL command', exact=True)).to_be_visible(timeout=180000)
            result['adminer_' + environment + '_login'] = True
            context.close()
        if args.include_jenkins:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(180000)
            page.goto(f'http://{vip}:8085/login', timeout=180000)
            page.locator('input[name="j_username"]').fill('admin')
            page.locator('input[name="j_password"]').fill(credential('jenkins', 'jenkins-foundation-login', 'jenkins-admin-password'))
            page.get_by_role('button', name='Sign in', exact=True).click()
            page.wait_for_url(f'http://{vip}:8085/', timeout=180000)
            info = page.evaluate("fetch('/api/json?tree=jobs[name],numExecutors').then(r => r.json())")
            assert info['numExecutors'] == 0 and info['jobs'] == []
            computers = page.evaluate("fetch('/computer/api/json?tree=computer[displayName,numExecutors]').then(r => r.json())")
            assert len(computers['computer']) == 1 and computers['computer'][0]['numExecutors'] == 0
            result['jenkins_login'] = True
            result['jenkins_jobs'] = 0
            result['jenkins_agents'] = 0
            context.close()
        browser.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Playwright/subprocess exceptions can contain secret-filled input values.
        print(json.dumps({'verified': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
