#!/usr/bin/env python3
"""Validate published DR links, real output assertions, syntax and image integrity."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
REVIEW = ROOT/'astra-review'
REAL = ROOT/'evidence/real/2026-10-24-local'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate():
    files = sorted(p for p in REVIEW.rglob('*') if p.is_file())
    files += sorted(p for p in REAL.rglob('*') if p.is_file())
    files += [ROOT/name for name in ['README.md','DR_INDEPENDENT_AUDIT_REPORT.md',
                                   'LOCAL_DISASTER_RECOVERY_TEST_REPORT.md','DR_PRESENTATION_FINAL_EVIDENCE.md']]
    files += [ROOT/'evidence/INDEX.md']
    count = 0
    for p in files:
        require(not p.is_symlink(), f'Symlink rejected: {p.relative_to(REPO)}')
        require(p.stat().st_size < 1_000_000, f'Unexpected large artifact: {p.name}')
        if p.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', p.read_text()):
                if '://' in link or link.startswith('#'):
                    continue
                target=(p.parent/unquote(link.split('#')[0])).resolve()
                require(target.is_relative_to(REPO) and target.exists(), f'Broken local link in {p.name}: {link}')
                count += 1
        elif p.suffix == '.py':
            ast.parse(p.read_text(), filename=p.name)
        elif p.suffix == '.sh':
            subprocess.run(['bash','-n',str(p)], check=True)
        elif p.suffix == '.json':
            json.loads(p.read_text())
        elif p.suffix in ('.yaml','.yml'):
            list(yaml.safe_load_all(p.read_text()))
    images=list((REVIEW/'screenshots').rglob('*.jpg'))
    require(len(images)==24,'Expected 24 unique screenshots')
    hashes=set()
    for p in images:
        with Image.open(p) as im:
            require(im.format=='JPEG' and min(im.size)>100, 'Invalid screenshot')
            im.verify()
        hashes.add(hashlib.sha256(p.read_bytes()).hexdigest())
    require(len(hashes)==24,'Duplicate published screenshot')
    for item in json.loads((REVIEW/'source-provenance.json').read_text())['artifacts']:
        require(hashlib.sha256((ROOT/item['published']).read_bytes()).hexdigest()==item['published_sha256'],
                'Artifact differs from provenance: '+item['published'])
    def read(name): return json.loads((REAL/name).read_text())
    rb=read('07-rollback/results.json')
    require((rb['config_before'],rb['config_changed'],rb['config_restored'])==('v1','v2','v1'),'Workload rollback evidence mismatch')
    require(rb['postgres_baseline']==rb['postgres_restored']=='1|checkpoint-v1','SQL baseline mismatch')
    require(rb['postgres_changed']!=rb['postgres_restored'] and rb['persistent_marker_preserved'],'Rollback mutation/marker evidence missing')
    require(not rb['r2_restore'] and not rb['pitr'],'Logical rollback mislabeled')
    rules=read('05-monitoring/rules.json')['data']['groups']
    allrules=[r for g in rules for r in g['rules']]
    require(len(allrules)==30 and all(r['health']=='ok' for r in allrules),'Rule count/health mismatch')
    require(read('05-monitoring/query.json')['data']['result'][0]['value'][1]=='1','Local target not UP')
    require(len(read('05-monitoring/alertmanager-firing.json'))>0 and read('05-monitoring/alertmanager-resolved.json')==[],'Alert lifecycle evidence mismatch')
    j=read('06-jenkins/restored-runtime.json')
    require(j['numExecutors']==0 and j['quietingDown'] and len(j['jobs'])==1,'Jenkins held-state mismatch')
    require(all(not job['buildable'] and not job['builds'] for job in j['jobs']),'Jenkins job not held')
    require('DR_RESTORED_ENCRYPTION_CHECK=true' in (REAL/'06-jenkins/restored-startup.log').read_text(),'Missing actual decryption check')
    receipt=read('06-jenkins/archive-receipt.json')
    require(receipt['master_key_preserved'] and receipt['hudson_secret_preserved'],'Encryption preservation missing')
    require('401 Unauthorized' in (REAL/'03-application/events.log').read_text(),'Missing application failure evidence')
    require(json.loads((REVIEW/'test-results/stopped-lab-recheck.json').read_text())['status']=='PASS','Cleanup recheck failed')
    return {'status':'PASS','files_checked':len(files),'markdown_relative_links_checked':count,
            'unique_jpeg_screenshots_decoded':len(images),'source_provenance_hashes_verified':True,
            'python_shell_json_yaml_syntax':'PASS','saved_runtime_assertions':'PASS',
            'scope':'Offline validation of retained evidence; does not re-execute recovery'}


if __name__=='__main__':
    print(json.dumps(validate(),indent=2))
