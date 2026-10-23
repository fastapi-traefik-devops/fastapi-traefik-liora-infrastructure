#!/usr/bin/env python3
"""Read Grafana in a real browser and capture provisioned dashboards without logging credentials."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

CHECK = 'arguments'


def main():
    global CHECK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', choices=['nonprod', 'prod'], required=True)
    parser.add_argument('--screenshots', type=Path, required=True)
    parser.add_argument('--legacy-only', action='store_true', help='Read old PROD dashboards before new-dashboard deployment approval')
    args = parser.parse_args()
    vip = {'nonprod': '192.168.77.16', 'prod': '192.168.77.17'}[args.cluster]
    config = Path.home() / '.kube' / ('config-dev-stage' if args.cluster == 'nonprod' else 'config-prod')
    CHECK = 'read Grafana login in memory'
    result = subprocess.run(['kubectl', '--kubeconfig', str(config), '-n', 'monitoring', 'get',
                             'secret', 'monitoring-grafana-admin', '-o', 'json'], capture_output=True, check=True)
    secret = json.loads(result.stdout)['data']
    username = base64.b64decode(secret['admin-user']).decode()
    password = base64.b64decode(secret['admin-password']).decode()
    url = f'http://{vip}:3000'
    uid = 'liora-' + args.cluster + '-operations'
    args.screenshots.mkdir(parents=True, exist_ok=True)
    evidence = {'cluster': args.cluster, 'grafana_version': '13.2.3', 'legacy_dashboards_loaded': [],
                'operations_deployed': not args.legacy_only, 'query_errors': [], 'screenshots': []}
    request_queries = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-proxy-server'])
        context = browser.new_context(viewport={'width': 1600, 'height': 1500}, device_scale_factor=1, color_scheme='dark')
        page = context.new_page()
        page.set_default_timeout(60000)
        CHECK = 'Grafana login'
        page.goto(url + '/login', timeout=60000)
        page.locator('input[name="user"]').fill(username)
        page.locator('input[name="password"]').fill(password)
        page.get_by_role('button', name='Log in', exact=True).click()
        page.wait_for_url(lambda current: current.startswith(url) and '/login' not in current)
        expect(page.locator('input[name="password"]')).to_have_count(0)

        def response_received(response):
            if '/api/ds/query' not in response.url:
                return
            try:
                request_queries.extend(q.get('expr', '') for q in response.request.post_data_json.get('queries', []))
            except Exception:
                pass
            if response.status >= 400:
                evidence['query_errors'].append({'status': response.status, 'check': CHECK})
                return
            try:
                payload = response.json()
                for ref, item in payload.get('results', {}).items():
                    if item.get('error'):
                        evidence['query_errors'].append({'ref': ref, 'error': 'Grafana datasource query error', 'check': CHECK})
            except Exception as error:
                # Chrome can release a completed response body while a dashboard
                # navigation is being processed. This is not a datasource failure.
                released = any(fragment in str(error) for fragment in [
                    'No resource with given identifier found', 'No data found for resource',
                    'Protocol error (Network.getResponseBody)', 'Response body is unavailable'])
                if response.status == 200 and released:
                    evidence['released_navigation_response_bodies'] = evidence.get('released_navigation_response_bodies', 0) + 1
                else:
                    evidence['query_errors'].append({'error': 'Datasource response could not be inspected', 'error_type': type(error).__name__, 'check': CHECK})

        page.on('response', response_received)
        search = page.evaluate("fetch('/api/search?type=dash-db').then(r => r.json())")
        legacy = ['platform-nodes', 'ingress-traefik', 'gitops-argocd', 'dev-stage-workloads' if args.cluster == 'nonprod' else 'prod-workloads']
        by_uid = {d['uid']: d for d in search}
        assert all(item in by_uid for item in legacy), 'Missing legacy dashboard'
        for existing in legacy:
            CHECK = 'legacy dashboard ' + existing
            page.goto(url + by_uid[existing]['url'] + '?theme=dark', timeout=60000)
            expect(page.get_by_text(by_uid[existing]['title'], exact=True).first).to_be_visible()
            page.wait_for_load_state('networkidle', timeout=30000)
            body = page.locator('body').inner_text()
            for error in ['Panel plugin not found', 'Error loading panel', 'Data is missing a number field', 'parse error:']:
                assert error not in body, 'Legacy dashboard rendered a panel error'
            evidence['legacy_dashboards_loaded'].append(existing)
        if not args.legacy_only:
            assert uid in by_uid, 'Operations dashboard not provisioned'

            def load(environment=None):
                request_queries.clear()
                params = {'from': 'now-1h', 'to': 'now', 'theme': 'dark'}
                if environment:
                    params['var-environment'] = environment
                page.goto(url + '/d/' + uid + '?' + urlencode(params), timeout=60000)
                expect(page.get_by_text('Liora / ' + args.cluster.upper() + ' Operations', exact=True).first).to_be_visible()
                expect(page.get_by_text('Request rate', exact=True).first).to_be_visible()
                page.wait_for_load_state('networkidle', timeout=30000)
                # Wait for panel canvas/layout after asynchronous query results.
                page.wait_for_timeout(1500)
                body = page.locator('body').inner_text()
                for error in ['Panel plugin not found', 'Error loading panel', 'Data is missing a number field', 'parse error:']:
                    assert error not in body, 'Rendered panel error'
                if environment:
                    service_queries = [q for q in request_queries if 'traefik_service_' in q and 'service=~' in q]
                    assert service_queries and all('app-(' + environment + ')-' in q for q in service_queries), 'Environment query interpolation differs'

            CHECK = 'Operations default view'
            load()
            # Grafana lazily paints panels near the viewport. Exercise the lower
            # default panels before capturing the complete overview.
            page.get_by_text('Pod readiness', exact=True).first.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)
            page.get_by_text('Request rate', exact=True).first.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)

            def screenshot(name):
                path = args.screenshots / (args.cluster + '-' + name + '.png')
                page.screenshot(path=str(path), full_page=True)
                evidence['screenshots'].append(path.name)

            def show_entire_panel(title):
                page.get_by_text(title, exact=True).first.evaluate('''element => {
                    let panel = element;
                    while (panel.parentElement) {
                        const box = panel.getBoundingClientRect();
                        if (box.width > 250 && box.width < 1300 && box.height > 100) {
                            panel.scrollIntoView({block: 'end'});
                            return;
                        }
                        panel = panel.parentElement;
                    }
                    element.scrollIntoView({block: 'end'});
                }''')

            screenshot('operations')
            if args.cluster == 'nonprod':
                evidence['environment_views'] = []
                for environment in ['dev', 'stage']:
                    CHECK = 'Environment selection ' + environment
                    load(environment)
                    evidence['environment_views'].append(environment)
                evidence['environment_query_filters_verified'] = True
                load()
            CHECK = 'Capacity section'
            page.get_by_text('04  /  Capacity, requests & limits · USE', exact=True).click()
            page.wait_for_load_state('networkidle', timeout=30000)
            show_entire_panel('Allocatable memory')
            page.wait_for_timeout(1500)
            screenshot('capacity')
            CHECK = 'Assurance section'
            page.get_by_text('04  /  Capacity, requests & limits · USE', exact=True).click()
            page.get_by_text('06  /  Database, certificates & assurance gaps', exact=True).click()
            page.wait_for_load_state('networkidle', timeout=30000)
            show_entire_panel('Assurance · not instrumented' if args.cluster == 'nonprod' else 'Assurance · coverage boundaries')
            expect(page.get_by_text('GRAFANA_OPERATIONS_DASHBOARDS.md', exact=True)).to_be_visible()
            page.wait_for_timeout(1500)
            screenshot('assurance')
            page.get_by_text('06  /  Database, certificates & assurance gaps', exact=True).click()
            comparison = '03  /  DEV ↔ STAGE comparison' if args.cluster == 'nonprod' else '03  /  Production service investigation'
            for title in [comparison, '05  /  Incidents & monitoring coverage']:
                CHECK = 'Collapsed section ' + title
                page.get_by_text(title, exact=True).click()
                page.wait_for_load_state('networkidle', timeout=30000)
                page.wait_for_timeout(1000)
                page.get_by_text(title, exact=True).click()
            evidence['all_sections_rendered'] = True
        if evidence['query_errors']:
            print(json.dumps({'query_errors': evidence['query_errors']}))
        assert not evidence['query_errors'], 'Browser reported datasource query errors'
        browser.close()
    (args.screenshots / (args.cluster + '-ui-verification.json')).write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Browser exceptions can contain secret-filled inputs; never echo the exception text/traceback.
        print(json.dumps({'verified': False, 'check': CHECK, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
