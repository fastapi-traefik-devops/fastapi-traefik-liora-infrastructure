#!/usr/bin/env python3
"""Verify held restored Jenkins state and existing admin login without running jobs."""

import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright


KUBE = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage'), '-n', 'jenkins']
URL = 'http://192.168.77.16:8085'
CURRENT_CHECK = 'arguments'

# Read-only administrative inspection. Decrypted values stay in the JVM and are
# reduced to booleans. Do not add job scheduling, credential binding or saves.
INSPECT = '''
import jenkins.model.Jenkins
import hudson.model.Job
import hudson.model.User
import hudson.util.Secret
import com.cloudbees.plugins.credentials.CredentialsProvider
import groovy.json.JsonOutput
def j = Jenkins.get()
def items = j.getAllItems()
def jobs = j.getAllItems(Job.class)
def credentials = []
([j] + items).each { item ->
  CredentialsProvider.lookupStores(item).findAll { it.getContext().is(item) }.each { store ->
    store.getDomains().each { domain ->
      store.getCredentials(domain).each { credential ->
        def record = [scope: item == j ? '/' : item.fullName, id: credential.id]
        // GitHubAppCredentials.getPassword() fetches an installation token.
        // Never call it during stored-credential inspection.
        def methods = credential.id == 'ghcr-write' ? ['getPassword'] : ['getPrivateKey']
        methods.each { method ->
          if (credential.metaClass.respondsTo(credential, method)) {
            def value = credential."${method}"()
            def text = value instanceof Secret ? value.getPlainText() : value?.toString()
            record[method == 'getPassword' ? 'password_present' : 'private_key_present'] =
              text != null && !text.isEmpty() && !(text.startsWith('{') && text.endsWith('}'))
          }
        }
        credentials.add(record)
      }
    }
  }
}
def branches = items.findAll { it.class.name.endsWith('WorkflowMultiBranchProject') }
def lock = new File('/usr/share/jenkins/ref/plugins.txt').readLines().findAll { it && !it.startsWith('#') }
def lockedIds = lock.collect { it.split(':', 2)[0] }
println JsonOutput.toJson([
  quiet: j.isQuietingDown(), executors: j.numExecutors, nodes: j.nodes.size(), queue: j.queue.items.size(),
  users: User.getAll().collect { it.id }.sort(), item_count: items.size(), job_count: jobs.size(),
  persisted_users: User.getAll().findAll { new File(it.rootDir, 'config.xml').isFile() }.collect { it.id }.sort(),
  jobs_disabled: jobs.every { it.isDisabled() },
  resume_disabled: jobs.every { it.isResumeBlocked() },
  multibranch_disabled: branches.every { it.isDisabled() },
  builds: jobs.sum { it.builds.size() } ?: 0,
  running_builds: jobs.sum { job -> job.builds.count { it.isBuilding() } } ?: 0,
  credentials: credentials,
  plugin_count: j.pluginManager.plugins.size(), failed_plugins: j.pluginManager.failedPlugins.size(),
  locked_plugins_match: lock.every { line -> def parts = line.split(':', 2); j.pluginManager.getPlugin(parts[0])?.version == parts[1] },
  additional_plugins: j.pluginManager.plugins.findAll { !lockedIds.contains(it.shortName) }.collect { [id: it.shortName, version: it.version] }
])
'''


def run(arguments):
    result = subprocess.run(KUBE + arguments, capture_output=True)
    if result.returncode:
        raise RuntimeError('Cluster inspection failed; private diagnostics suppressed')
    return result.stdout


def main():
    global CURRENT_CHECK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('restore_directory', type=Path)
    args = parser.parse_args()
    directory = args.restore_directory
    expected = json.loads((directory / 'expected-files.json').read_text())
    expected_builds = sum(name.startswith('jobs/') and name.endswith('/build.xml') for name in expected)
    expected_items = sum(name.startswith('jobs/') and name.endswith('/config.xml') for name in expected)
    expected_users = sum(name.startswith('users/') and name.endswith('/config.xml') for name in expected)
    secret = json.loads(run(['get', 'secret', 'jenkins-foundation-login', '-o', 'json']))
    password = base64.b64decode(secret['data']['jenkins-admin-password']).decode()
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
              urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(path, data=None, headers=None):
        req = urllib.request.Request(URL + path, data=data,
                                     headers={'Authorization': 'Basic ' + auth, **(headers or {})})
        with opener.open(req, timeout=120) as response:
            return response.read()

    CURRENT_CHECK = 'admin-api-login'
    who = json.loads(request('/whoAmI/api/json'))
    if who.get('name') != 'admin' or not who.get('authenticated'):
        raise RuntimeError('Current admin authentication failed')
    crumb = json.loads(request('/crumbIssuer/api/json'))
    raw = request('/scriptText', urllib.parse.urlencode({'script': INSPECT}).encode(),
                  {crumb['crumbRequestField']: crumb['crumb']})
    report = json.loads(raw)
    with os.fdopen(os.open(directory / 'runtime-inspection.json', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump(report, stream)
    CURRENT_CHECK = 'execution-hold'
    if not (report['quiet'] and report['executors'] == 0 and report['nodes'] == 0 and report['queue'] == 0
            and report['jobs_disabled'] and report['resume_disabled'] and report['multibranch_disabled']
            and report['running_builds'] == 0 and report['failed_plugins'] == 0):
        raise RuntimeError('Restored execution hold is not verified')
    CURRENT_CHECK = 'state-counts'
    if report['item_count'] != expected_items or report['builds'] != expected_builds or len(report['persisted_users']) != expected_users:
        raise RuntimeError('Restored state counts differ')
    CURRENT_CHECK = 'preserved-plugin-versions'
    if not report['locked_plugins_match'] or any('plugins/' + plugin['id'] + '.jpi' not in expected for plugin in report['additional_plugins']):
        raise RuntimeError('Loaded plugin versions or additional plugins differ from the source')
    credential_ids = {(value['scope'], value['id']) for value in report['credentials']}
    CURRENT_CHECK = 'credential-scopes-and-decryption'
    if credential_ids != {('app-ci', 'github-ci-app'), ('trusted', 'ghcr-write'), ('trusted', 'gitops-app')}:
        raise RuntimeError('Credential IDs or scopes differ')
    for record in report['credentials']:
        field = 'password_present' if record['id'] == 'ghcr-write' else 'private_key_present'
        if not record.get(field):
            raise RuntimeError('Credential decryption check failed')
    admin_path = next(name for name in expected if name.startswith('users/admin_') and name.endswith('/config.xml'))
    CURRENT_CHECK = 'admin-password-hash'
    current = ET.fromstring(run(['exec', 'deployment/jenkins', '--', 'cat', '/var/jenkins_home/' + admin_path]))
    saved = ET.fromstring((directory / 'current-admin.xml').read_bytes())
    if current.findtext('.//passwordHash') != saved.findtext('.//passwordHash'):
        raise RuntimeError('Current admin password hash changed')
    CURRENT_CHECK = 'preserved-encryption-keys'
    for key in ['secrets/master.key', 'secrets/hudson.util.Secret', 'secrets/hudson.model.User.DIRNAMES']:
        data = run(['exec', 'deployment/jenkins', '--', 'cat', '/var/jenkins_home/' + key])
        if hashlib.sha256(data).hexdigest() != expected[key]:
            raise RuntimeError('Preserved encryption or user-directory key changed')
    CURRENT_CHECK = 'controller-egress-hold'
    probe = run(['exec', 'deployment/jenkins', '--', 'sh', '-c',
                 'if wget -T 3 -q -O /dev/null http://1.1.1.1 >/dev/null 2>&1; then echo allowed; else echo blocked; fi'])
    if probe.strip() != b'blocked':
        raise RuntimeError('Controller egress hold did not block the baseline destination')
    CURRENT_CHECK = 'admin-browser-login'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--no-proxy-server'])
        page = browser.new_page()
        page.goto(URL + '/login', timeout=180000)
        page.locator('input[name="j_username"]').fill('admin')
        page.locator('input[name="j_password"]').fill(password)
        page.get_by_role('button', name='Sign in', exact=True).click()
        page.wait_for_url(URL + '/', timeout=180000)
        identity = page.evaluate("fetch('/whoAmI/api/json').then(r => r.json())")
        if identity.get('name') != 'admin':
            raise RuntimeError('Browser admin authentication failed')
        browser.close()
    report.update(admin_login_preserved=True, browser_login=True, encryption_keys_verified=True,
                  egress_probe_blocked=True, jobs_executed_by_verifier=0)
    target = directory / 'runtime-acceptance.json'
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'verified': False, 'check': CURRENT_CHECK, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
