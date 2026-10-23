#!/usr/bin/env python3
"""Operate the approved existing main/publisher checkpoint; never print credentials."""
import argparse
import base64
import http.cookiejar
import hashlib
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


def hold(request, related_prs=()):
    if any(type(number) is not int or number < 1 for number in related_prs):
        raise ValueError('Related PR numbers must be positive integers')
    jobs = ['app-ci/main', 'trusted/publish'] + [f'app-ci/PR-{number}' for number in related_prs]
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
CHECKPOINT_JOBS.each { name ->
 j.getItemByFullName(name)?.builds?.findAll { it.isBuilding() }?.each { b ->
  b.getExecutor()?.interrupt(Result.ABORTED)
  b.getExecution()?.interrupt(Result.ABORTED)
 }
}
println 'Checkpoint execution hold restored'
'''.replace('CHECKPOINT_JOBS', json.dumps(jobs)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'hold', 'repair-tracker', 'approve-publisher', 'start', 'poll'])
    p.add_argument('--pr', type=int, action='append', default=[], help='Related checkpoint PR to abort during hold; repeat as needed')
    args = p.parse_args()
    if args.pr and args.action != 'hold':
        p.error('--pr is only valid with hold')
    request = client()
    if args.action == 'hold':
        print(hold(request, args.pr).decode().strip())
    elif args.action == 'status':
        state = HELPER['inspect'](request)
        print(json.dumps({'quiet': state['quiet'], 'executors': state['executors'], 'queue': state['queue'],
                          'running': state['running'], 'jobs': state['jobs']}))
    elif args.action == 'approve-publisher':
        definition = subprocess.check_output(['git', '-C', str(ROOT.parent / 'fastapi-traefik-liora-application'),
                                               'show', 'HEAD:Jenkinsfile.promote'])
        expected = hashlib.sha256(definition).hexdigest()
        print(script(request, """
import groovy.json.JsonOutput
import org.jenkinsci.plugins.scriptsecurity.scripts.ScriptApproval
import org.jenkinsci.plugins.scriptsecurity.scripts.languages.GroovyLanguage
def j=jenkins.model.Jenkins.get();def job=j.getItemByFullName('trusted/publish')
assert j.isQuietingDown() && job.isDisabled() && !job.builds.any{it.isBuilding()}
def body=job.definition.script
def hash=java.security.MessageDigest.getInstance('SHA-256').digest(body.getBytes('UTF-8')).encodeHex().toString()
assert hash=='EXPECTED_HASH'
def approval=ScriptApproval.get()
def pending=approval.pendingScripts.find{it.script==body}
if(pending!=null){approval.approveScript(pending.hash)}
assert approval.isScriptApproved(body,GroovyLanguage.get())
println JsonOutput.toJson([publisherApproved:true,definitionSha256:hash,otherScriptsApproved:false])
""".replace('EXPECTED_HASH', expected)).decode().strip())
    elif args.action == 'repair-tracker':
        print(script(request, """
import groovy.json.JsonOutput
import org.jenkinsci.plugins.pipeline.modeldefinition.actions.DeclarativeJobPropertyTrackerAction
def j=jenkins.model.Jenkins.get()
assert j.isQuietingDown() && j.queue.items.size()==0
assert j.getAllItems(hudson.model.Job.class).every{it.isDisabled() && !it.builds.any{b->b.isBuilding()}}
def repaired=[]
['app-ci/main','trusted/publish'].each{name->
 def job=j.getItemByFullName(name)
 def action=job.getAction(DeclarativeJobPropertyTrackerAction.class)
 if(action!=null){
  def broken=false
  try{action.getTriggers()}catch(NullPointerException e){broken=true}
  if(broken){job.removeAction(action);job.save();repaired.add(name)}
 }
}
println JsonOutput.toJson([repaired:repaired,historyPreserved:true])
""").decode().strip())
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
