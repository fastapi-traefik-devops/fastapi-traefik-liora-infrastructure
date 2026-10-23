#!/usr/bin/env python3
"""Provision scoped coordinator RBAC and private R2 Secrets without printing values."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import yaml

ROOT=Path(__file__).resolve().parents[2]


def kube(config, args, obj=None):
    result=subprocess.run(['kubectl','--kubeconfig',str(config)]+args,
        input=json.dumps(obj).encode() if obj is not None else None,capture_output=True)
    if result.returncode:
        raise RuntimeError('Kubernetes provisioning failed; inspect resource metadata privately')
    return json.loads(result.stdout) if result.stdout.strip().startswith(b'{') else None


def provision(directory):
    data=yaml.safe_load((directory/'recovery.yaml').read_text())['database_backups']
    config={'version':1,'state_dir':'/var/lib/liora-backups','listen':'192.168.77.250',
            'r2':{k:data[k] for k in ['endpoint','bucket','access_key_id','secret_access_key']},'clusters':{}}
    for cluster, filename, environments, vip in [('nonprod','config-dev-stage',['dev','stage'],'192.168.77.16'),
                                                ('prod','config-prod',['prod'],'192.168.77.17')]:
        cfg=Path.home()/'.kube'/filename
        kube(cfg,['apply','--server-side','--field-manager=liora-backup-bootstrap','-f',
                  str(ROOT/'infrastructure/backup-coordinator'/('rbac-'+cluster+'.yaml'))])
        for attempt in range(30):
            secret=kube(cfg,['-n','cnpg-system','get','secret','backup-coordinator-token','-o','json'])
            if secret.get('data',{}).get('token'):break
            time.sleep(1)
        else:raise RuntimeError('Coordinator token generation timeout')
        view=kube(cfg,['config','view','--minify','-o','json'])
        config['clusters'][cluster]={'server':view['clusters'][0]['cluster']['server'],
            'token':base64.b64decode(secret['data']['token']).decode(),
            'ca_pem':base64.b64decode(secret['data']['ca.crt']).decode(),
            'alertmanager':'http://'+vip+':9093'}
        for env in environments:
            target={'apiVersion':'v1','kind':'Secret','metadata':{'name':'r2-backup','namespace':'app-'+env},
                'type':'Opaque','data':{key:base64.b64encode(data[field].encode()).decode()
                    for key,field in [('ACCESS_KEY_ID','access_key_id'),('SECRET_ACCESS_KEY','secret_access_key'),('ENDPOINT_URL','endpoint'),('REGION','region')]}}
            existing=kube(cfg,['-n','app-'+env,'get','secret','r2-backup','--ignore-not-found','-o','json'])
            if existing:
                if any(existing.get('data',{}).get(key,value)!=value for key,value in target['data'].items()):raise RuntimeError('Existing R2 Secret differs; no automatic rotation')
                kube(cfg,['apply','--server-side','--field-manager=liora-r2-private','-f','-'],target)
            else:kube(cfg,['create','-f','-'],target)
    target=directory/'backup-coordinator.json'
    if target.exists() and json.loads(target.read_text())!=config:
        raise RuntimeError('Existing private coordinator configuration differs; review before replacement')
    target.write_text(json.dumps(config,indent=2)+'\n');target.chmod(0o600)
    print('Coordinator RBAC, private recovery configuration and R2 Secret references prepared; values suppressed')


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--recovery-dir',type=Path,default=ROOT/'recovery');args=parser.parse_args()
    try:provision(args.recovery_dir)
    except Exception as error:raise SystemExit('Backup provisioning stopped: '+type(error).__name__)
