#!/usr/bin/env python3
"""Read GitHub App installation access with runtime Jenkins keys; never print keys/JWTs."""

import base64
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def main():
    root = Path(__file__).resolve().parents[2]
    import runpy
    helper = runpy.run_path(str(root / 'scripts/kubernetes/manual-jenkins-ci.py'))
    request = helper['client']()
    before = helper['inspect'](request)
    credentials = json.loads(helper['script'](request, """
import com.cloudbees.plugins.credentials.CredentialsProvider
import groovy.json.JsonOutput
def result = [:]
['app-ci':'github-ci-app', 'trusted':'gitops-app'].each { folder, id ->
 def item = jenkins.model.Jenkins.get().getItemByFullName(folder)
 CredentialsProvider.lookupStores(item).each { store -> store.domains.each { domain ->
   store.getCredentials(domain).findAll { it.id == id }.each { c ->
    result[id] = [id:c.appID, key:c.privateKey.plainText]
   }
 } }
}
println JsonOutput.toJson(result)
"""))
    def encoded(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=')
    repositories = ['fastapi-traefik-liora-application', 'fastapi-traefik-liora-infrastructure']
    summary = []
    for role in ['ci', 'gitops']:
        credential = credentials['github-ci-app' if role == 'ci' else 'gitops-app']
        app_id = credential['id']
        key = serialization.load_pem_private_key(credential['key'].encode(), password=None)
        now = int(time.time())
        header = encoded(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode())
        claims = encoded(json.dumps({'iat': now - 60, 'exp': now + 540, 'iss': app_id}).encode())
        unsigned = header + b'.' + claims
        signature = key.sign(unsigned, padding.PKCS1v15(), hashes.SHA256())
        token = (unsigned + b'.' + encoded(signature)).decode()
        for repo in repositories:
            github_request = urllib.request.Request('https://api.github.com/repos/fastapi-traefik-devops/' + repo + '/installation',
                                             headers={'Authorization': 'Bearer ' + token,
                                                      'Accept': 'application/vnd.github+json',
                                                      'User-Agent': 'liora-phase9-read-only-audit'})
            try:
                with urllib.request.urlopen(github_request, timeout=30) as response:
                    data = json.load(response)
                    summary.append({'role': role, 'repository': repo, 'status': response.status,
                                    'permissions': data['permissions'],
                                    'repository_selection': data['repository_selection']})
            except urllib.error.HTTPError as error:
                summary.append({'role': role, 'repository': repo, 'status': error.code,
                                'installation_access_verified': False})
    # Public rule endpoints reveal rulesets, but classic protection needs an
    # installation token and Administration read. Record unverifiable responses.
    api = 'https://api.github.com'
    def api_call(path, auth, method='GET', body=None):
        req = urllib.request.Request(api + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + auth, 'Accept': 'application/vnd.github+json',
                     'User-Agent': 'liora-phase9-read-only-audit', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.load(response) if response.status != 204 else None
        except urllib.error.HTTPError as error:
            return error.code, None
    # The final loop used the GitOps App JWT. Mint only a temporary token; no Git,
    # branch-rule, repository-content or Jenkins configuration writes occur.
    base = '/repos/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure'
    status, installation = api_call(base + '/installation', token)
    rules = {'installation_status': status}
    if status == 200:
        status, issued = api_call('/app/installations/' + str(installation['id']) + '/access_tokens',
            token, 'POST', {'repositories': ['fastapi-traefik-liora-infrastructure']})
        rules['temporary_token_status'] = status
        if status == 201:
            temporary = issued['token']
            try:
                for name, path in [('classic_protection', '/branches/main/protection'),
                                   ('rulesets', '/rulesets?includes_parents=true'),
                                   ('main_rules', '/rules/branches/main')]:
                    code, data = api_call(base + path, temporary)
                    rules[name] = {'status': code, 'data': data if code == 200 else None}
            finally:
                rules['temporary_token_revocation_status'] = api_call('/installation/token', temporary, 'DELETE')[0]
    after = helper['inspect'](request)
    if before != after:
        raise RuntimeError('Jenkins state changed during audit')
    result = {'installations': summary, 'branch_audit': rules, 'jenkins_state_unchanged': True}
    target = root / '.local-work/private/phase9/github-app-access-current.json'
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'access_check_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
