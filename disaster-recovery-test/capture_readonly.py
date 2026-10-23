#!/usr/bin/env python3
"""Capture allowlisted read-only metadata. Never read Secret values or run helpers."""
from pathlib import Path
import datetime
import json
import subprocess
import sys

REMOTE = r'''
import pathlib,subprocess,json,datetime
r=pathlib.Path.home()/'fastapi-traefik-liora-infrastructure'
out={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'clusters':{}}
for cluster in ['dev-stage','prod']:
 b=['kubectl','--kubeconfig='+str(pathlib.Path.home()/'.kube'/('config-'+cluster)),'--request-timeout=20s']
 records={}
 for kind in ['nodes','deployments.apps','statefulsets.apps','persistentvolumeclaims','applications.argoproj.io','ingresses.networking.k8s.io']:
  args=b+['get',kind,'-A','-o','json']
  p=subprocess.run(args,capture_output=True,text=True)
  if p.returncode:records[kind]={'read_failed':True};continue
  rows=[]
  for x in json.loads(p.stdout)['items']:
   m=x['metadata'];s=x.get('spec',{});status=x.get('status',{})
   row={'namespace':m.get('namespace'),'name':m['name'],'uid':m['uid']}
   if kind=='nodes':row['ready']=next((c['status'] for c in status.get('conditions',[]) if c['type']=='Ready'),None)
   elif kind in ['deployments.apps','statefulsets.apps']:
    row.update(replicas=s.get('replicas'),images=[c['image'] for c in s['template']['spec']['containers']])
   elif kind=='persistentvolumeclaims':row.update(volume=s.get('volumeName'),phase=status.get('phase'))
   elif kind=='applications.argoproj.io':row.update(spec=s,sync=status.get('sync',{}).get('status'),health=status.get('health',{}).get('status'))
   elif kind.startswith('ingresses'):row['spec']=s
   rows.append(row)
  records[kind]=sorted(rows,key=lambda x:(x.get('namespace') or '',x['name']))
 out['clusters'][cluster]=records
out['recovery_presence_only']={f:(r/'recovery'/f).is_file() for f in ['recovery.yaml','.env','backup-coordinator.json','LIORA-id_ed25519']}
out['repo_revision']=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip()
print(json.dumps(out))
'''

def main():
    phase=sys.argv[1]
    if phase not in ['before','after']:raise SystemExit('Expected before or after')
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes',
                      '-i',str(Path.home()/'.ssh/liora-argocd'),'Liora','python3 -'],
                     input=REMOTE,text=True,capture_output=True,timeout=150)
    if p.returncode:
        value={'read_failed':True,'exit_code':p.returncode,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    else:value=json.loads(p.stdout)
    target=Path(__file__).parent/'evidence/real'/('live-'+phase+'.json')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'phase':phase,'read_failed':value.get('read_failed',False),'path':str(target)}))

if __name__=='__main__':main()
