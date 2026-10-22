#!/usr/bin/env python3
"""Operate the approved existing main/publisher checkpoint; never print credentials."""
import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import runpy
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(ROOT / 'scripts/kubernetes/manual-jenkins-ci.py'))
KUBE = ['kubectl', '--kubeconfig=' + str(Path.home() / '.kube/config-dev-stage')]


def client():
    result = subprocess.run(KUBE + ['-n', 'jenkins', 'get', 'secret', 'jenkins-foundation-login', '-o', 'json'], capture_output=True, check=True)
    password = base64.b64decode(json.loads(result.stdout)['data']['jenkins-admin-password']).decode()
    auth = base64.b64encode(('admin:' + password).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path, data=None, headers=None):
        req = urllib.request.Request('http://192.168.77.16:8085' + path, data=data,
                                     headers={'Authorization': 'Basic ' + auth, **(headers or {})})
        with opener.open(req, timeout=120) as response:
            return response.read()
    if json.loads(request('/whoAmI/api/json')).get('name') != 'admin':
        raise RuntimeError('Current administrator authentication failed')
    return request


def script(request, text):
    return HELPER['script'](request, text)


def hold(request):
    # Preserve history; stop only new checkpoint execution, never unrelated workloads.
    return script(request, '''
import jenkins.model.Jenkins
import hudson.model.Job
import hudson.model.Result
def j = Jenkins.get()
j.doQuietDown()
j.getAllItems(Job.class).each { job ->
 job.setDisabled(true)
 job.getTriggers().values().toList().each { job.removeTrigger(it.descriptor) }
 job.save()
}
j.queue.items.each { j.queue.cancel(it) }
['app-ci/main','trusted/publish','app-ci/PR-62'].each { name ->
 j.getItemByFullName(name)?.builds?.findAll { it.isBuilding() }?.each { b ->
  b.getExecutor()?.interrupt(Result.ABORTED)
  b.getExecution()?.interrupt(Result.ABORTED)
 }
}
println 'Checkpoint execution hold restored'
''')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'hold', 'start', 'poll'])
    args = p.parse_args()
    request = client()
    if args.action == 'hold':
        print(hold(request).decode().strip())
    elif args.action == 'status':
        state = HELPER['inspect'](request)
        print(json.dumps({'quiet': state['quiet'], 'executors': state['executors'], 'queue': state['queue'],
                          'running': state['running'], 'jobs': state['jobs']}))
    elif args.action == 'start':
        result = script(request, '''
import jenkins.model.Jenkins
import hudson.model.Job
import hudson.model.Cause
import groovy.json.JsonOutput
def j = Jenkins.get()
assert j.isQuietingDown() && j.queue.items.size() == 0
assert j.numExecutors == 0
assert j.getAllItems(Job.class).every { it.isDisabled() && it.getTriggers().isEmpty() }
def main = j.getItemByFullName('app-ci/main')
def publisher = j.getItemByFullName('trusted/publish')
[main,publisher].each { it.setDisabled(false); it.save() }
j.doCancelQuietDown()
def requested=main.nextBuildNumber
assert main.scheduleBuild2(0, new hudson.model.CauseAction(new Cause.UserIdCause())) != null
println JsonOutput.toJson([requested:requested, publisherNext:publisher.nextBuildNumber])
''')
        print(result.decode().strip())
    elif args.action == 'poll':
        print(script(request, '''
import jenkins.model.Jenkins
import hudson.model.Job
import hudson.triggers.SCMTrigger
def j = Jenkins.get()
assert j.queue.items.size() == 0
assert j.getAllItems(Job.class).every { !it.builds.any { b -> b.isBuilding() } }
assert j.getAllItems(Job.class).findAll { !(it.fullName in ['app-ci/main','trusted/publish']) }.every { it.isDisabled() && it.getTriggers().isEmpty() }
def main = j.getItemByFullName('app-ci/main')
assert main.lastBuild.result.toString() == 'SUCCESS'
assert j.getItemByFullName('trusted/publish').lastBuild.result.toString() == 'SUCCESS'
assert main.getTriggers().isEmpty()
main.addTrigger(new SCMTrigger('H/2 * * * *'))
main.save()
println 'Only app-ci/main SCM polling enabled: H/2 * * * *'
''').decode().strip())


if __name__ == '__main__':
    os.umask(0o077)
    main()
