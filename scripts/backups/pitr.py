#!/usr/bin/env python3
"""Isolated, sequential CNPG PITR with controlled markers and real application UI.

Failure retains the namespace, marker and evidence. Cleanup is UID/run guarded.
No source endpoints, image references or database bootstrap are changed.
"""
import argparse
import base64
import copy
import datetime as dt
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import uuid

import boto3
from botocore.config import Config
from playwright.sync_api import sync_playwright, expect
import yaml

ROOT=Path(__file__).resolve().parents[2]
PLUGIN='barman-cloud.cloudnative-pg.io'


def kube(config, args, obj=None):
    result=subprocess.run(['kubectl','--kubeconfig',str(config),'--request-timeout=30s']+args,
        input=json.dumps(obj).encode() if obj is not None else None,capture_output=True,timeout=60)
    if result.returncode:
        raise RuntimeError('Kubernetes operation failed; resource identifiers retained in evidence')
    return json.loads(result.stdout) if result.stdout.lstrip().startswith((b'{',b'[')) else None


def create(config,obj):
    return kube(config,['create','-f','-','-o','json'],obj)


def sql(config, namespace, primary, query):
    result=subprocess.run(['kubectl','--kubeconfig',str(config),'-n',namespace,'exec',primary,
        '-c','postgres','--','psql','-v','ON_ERROR_STOP=1','-U','postgres','-d','app','-Atc',query],
        capture_output=True,timeout=45)
    if result.returncode:raise RuntimeError('SQL checkpoint failed; do not advance')
    return result.stdout.decode().strip()


def make_restore(source, store, namespace, backup_id, target_time, environment):
    store=copy.deepcopy(store);store['metadata']={'name':'source-archive','namespace':namespace}
    store.pop('status',None);store['spec'].pop('retentionPolicy',None)
    cluster={'apiVersion':'postgresql.cnpg.io/v1','kind':'Cluster',
        'metadata':{'name':'pitr-db','namespace':namespace,'labels':{'liora.aprt.info/pitr-test':'true'}},
        'spec':{'instances':1,'enablePDB':False,'imageName':source['spec']['imageName'],
          'enableSuperuserAccess':True,'superuserSecret':{'name':'cnpg-superuser'},
          'storage':copy.deepcopy(source['spec']['storage']),'resources':copy.deepcopy(source['spec']['resources']),
          'postgresql':copy.deepcopy(source['spec']['postgresql']),
          'bootstrap':{'recovery':{'source':'source','recoveryTarget':{'backupID':backup_id,'targetTime':target_time}}},
          'externalClusters':[{'name':'source','plugin':{'name':PLUGIN,'parameters':{
              'barmanObjectName':'source-archive','serverName':'liora-'+environment}}}]}}
    assert 'plugins' not in cluster['spec'] and 'retentionPolicy' not in store['spec']
    return cluster,store


def cleanup_guard(record,namespace):
    assert record['environment'] in ['dev','stage','prod']
    assert re.fullmatch('pitr-'+record['environment']+'-[a-f0-9]{8}',record['namespace'])
    assert namespace['metadata']['name']==record['namespace']
    assert namespace['metadata']['uid']==record['namespace_uid']
    assert namespace['metadata']['labels']['liora.aprt.info/pitr-run']==record['run_id']
    assert re.fullmatch('pitr_probe_[a-f0-9]{12}',record['marker_table'])


def cleanup(config, record):
    ns=record['namespace'];live='app-'+record['environment']
    obj=kube(config,['get','namespace',ns,'-o','json']);cleanup_guard(record,obj)
    claims=kube(config,['-n',ns,'get','pvc','-o','json'])['items']
    assert all(x['metadata'].get('labels',{}).get('cnpg.io/cluster')=='pitr-db' for x in claims)
    record['test_volumes']=[{'pvc':x['metadata']['name'],'uid':x['metadata']['uid'],'pv':x['spec']['volumeName']} for x in claims]
    kube(config,['delete','namespace',ns,'--wait=false'])
    for _ in range(120):
        left=kube(config,['get','namespace',ns,'--ignore-not-found','-o','json'])
        if not left:break
        time.sleep(2)
    else:raise RuntimeError('Temporary namespace cleanup timeout')
    for v in record['test_volumes']:
        for _ in range(90):
            if not kube(config,['get','pv',v['pv'],'--ignore-not-found','-o','json']):break
            time.sleep(2)
        else:raise RuntimeError('Temporary PV cleanup timeout')
    if record.get('marker_table_created'):
        source=kube(config,['-n',live,'get','cluster','liora-db','-o','json'])
        sql(config,live,source['status']['currentPrimary'],'DROP TABLE public.'+record['marker_table']+';')
    record['cleanup_complete']=True


def browser_check(url, credentials):
    # No screenshots, traces, storage-state or filled-value diagnostics.
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-proxy-server'])
        page=browser.new_page();page.set_default_timeout(60000)
        assert page.goto(url+'/api/v1/utils/health-check/').status==200
        assert page.locator('body').inner_text()=='true'
        page.goto(url+'/login')
        page.get_by_placeholder('Email',exact=True).fill(credentials['email'])
        page.get_by_placeholder('Password',exact=True).fill(credentials['password'])
        with page.expect_response(lambda r:'/api/v1/login/access-token' in r.url and r.request.method=='POST') as response:
            page.get_by_role('button',name='Log In',exact=True).click()
        assert response.value.status==200;page.wait_for_url(url+'/')
        title='pitr-disposable-'+uuid.uuid4().hex[:8]
        page.goto(url+'/items');page.get_by_role('button',name='Add Item',exact=True).click()
        page.get_by_placeholder('Title',exact=True).fill(title)
        page.get_by_placeholder('Description',exact=True).fill('Isolated restored application verification')
        with page.expect_response(lambda r:r.url.endswith('/api/v1/items/') and r.request.method=='POST') as created:
            page.get_by_role('button',name='Save',exact=True).click()
        assert created.value.status in [200,201];item=created.value.json()['id']
        row=page.get_by_role('row').filter(has_text=title);expect(row).to_be_visible()
        row.get_by_role('button').click();page.get_by_role('button',name='Edit Item',exact=True).click()
        page.get_by_placeholder('Title',exact=True).fill(title+'-updated')
        with page.expect_response(lambda r:r.request.method=='PUT' and item in r.url) as updated:
            page.get_by_role('button',name='Save',exact=True).click()
        assert updated.value.status==200;page.reload();expect(page.get_by_role('row').filter(has_text=title+'-updated')).to_be_visible()
        result=page.evaluate('''async id=>{const headers={Authorization:'Bearer '+localStorage.getItem('access_token')};
            const removed=await fetch('/api/v1/items/'+id,{method:'DELETE',headers});
            const absent=await fetch('/api/v1/items/'+id,{headers});return [removed.status,absent.status]}''',item)
        assert result==[200,404];browser.close()


def application_check(config, namespace, source_namespace, record):
    backend=kube(config,['-n',source_namespace,'get','deployment','backend','-o','json'])
    frontend=kube(config,['-n',source_namespace,'get','deployment','frontend','-o','json'])
    cm=kube(config,['-n',source_namespace,'get','configmap','backend-config','-o','json'])
    cm['metadata']={'name':'backend-config','namespace':namespace};cm['data']['POSTGRES_SERVER']='pitr-db-rw';create(config,cm)
    containers=[copy.deepcopy(d['spec']['template']['spec']['containers'][0]) for d in [backend,frontend]]
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'restored-app','namespace':namespace},'spec':{
        'containers':containers,'imagePullSecrets':[{'name':'ghcr-pull-secret'}],
        'automountServiceAccountToken':False,'restartPolicy':'Never'}}
    create(config,pod)
    for _ in range(180):
        obj=kube(config,['-n',namespace,'get','pod','restored-app','-o','json'])
        statuses=obj.get('status',{}).get('containerStatuses',[])
        if len(statuses)==2 and all(x['ready'] for x in statuses):break
        time.sleep(2)
    else:raise RuntimeError('Restored application Pod readiness timeout')
    record['application_images']={c['name']:c['image'] for c in containers}
    for status in statuses:
        assert status['imageID'].split('@')[-1]==record['application_images'][status['name']].split('@')[-1]
    holders=[socket.socket(),socket.socket()]
    for sock in holders:sock.bind(('127.0.0.1',0))
    ports=[s.getsockname()[1] for s in holders]
    for s in holders:s.close()
    log=Path(record['evidence_directory'])/'port-forward.log'
    with log.open('wb') as output:
        forward=subprocess.Popen(['kubectl','--kubeconfig',str(config),'-n',namespace,'port-forward','--address=127.0.0.1',
            'pod/restored-app',str(ports[0])+':8000',str(ports[1])+':80'],stdout=output,stderr=subprocess.STDOUT)
        class Proxy(BaseHTTPRequestHandler):
            def handle_request(self):
                connection=http.client.HTTPConnection('127.0.0.1',ports[0] if self.path.startswith('/api/') else ports[1],timeout=30)
                body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                headers={k:v for k,v in self.headers.items() if k.lower() not in ['host','connection','transfer-encoding']}
                connection.request(self.command,self.path,body=body,headers=headers);response=connection.getresponse();data=response.read()
                self.send_response(response.status)
                for k,v in response.getheaders():
                    if k.lower() not in ['transfer-encoding','connection','content-length']:self.send_header(k,v)
                self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass  # Browser navigation cancelled a response.
                finally:connection.close()
            do_GET=do_POST=do_PUT=do_DELETE=do_OPTIONS=handle_request
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
        serving=False
        try:
            for _ in range(30):
                try:
                    with socket.create_connection(('127.0.0.1',ports[0]),timeout=1):break
                except OSError:time.sleep(1)
            else:raise RuntimeError('Isolated application forward unavailable')
            threading.Thread(target=server.serve_forever,daemon=True).start();serving=True
            secret=kube(config,['-n',source_namespace,'get','secret','backend-secrets','-o','json'])
            browser_check('http://127.0.0.1:'+str(server.server_address[1]),
                {'email':cm['data']['FIRST_SUPERUSER'],'password':base64.b64decode(secret['data']['FIRST_SUPERUSER_PASSWORD']).decode()})
            record['restored_frontend_backend_login_crud']=True
            record['application_access']='localhost-only temporary frontend/API proxy; no live routing change'
        finally:
            if serving:server.shutdown()
            server.server_close();forward.terminate()
            try:forward.wait(timeout=10)
            except subprocess.TimeoutExpired:forward.kill();forward.wait()


def run(args):
    env=args.environment;cfg=Path.home()/'.kube'/('config-prod' if env=='prod' else 'config-dev-stage');live='app-'+env
    directory=args.evidence.resolve();directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    began=time.monotonic()
    run_id=uuid.uuid4().hex;record={'environment':env,'run_id':run_id,'namespace':'pitr-'+env+'-'+run_id[:8],
        'marker_table':'pitr_probe_'+run_id[:12],'evidence_directory':str(directory),'rto_started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'success':False,'cleanup_complete':False}
    path=directory/'result.json'
    def save():path.write_text(json.dumps(record,indent=2)+'\n');path.chmod(0o600)
    save()
    try:
        for cluster in ['dev-stage','prod']:
            existing=kube(Path.home()/'.kube'/('config-'+cluster),['get','clusters.postgresql.cnpg.io','-A','-o','json'])['items']
            if any(c['metadata']['namespace'].startswith('pitr-') for c in existing):raise RuntimeError('Previous isolated restore exists; inspect before creating another')
        source=kube(cfg,['-n',live,'get','cluster','liora-db','-o','json']);primary=source['status']['currentPrimary']
        backup=kube(cfg,['-n',live,'get','backup',args.backup,'-o','json']);assert backup['status']['phase']=='completed';assert backup['spec']['method']=='plugin'
        backup_id=backup['status'].get('backupId')
        if not backup_id:raise RuntimeError('Completed backup has no physical backup ID')
        record.update(backup_resource=args.backup,physical_backup_id=backup_id)
        table=record['marker_table']
        sql(cfg,live,primary,'CREATE TABLE public.'+table+' (name text PRIMARY KEY);')
        record['marker_table_created']=True;save()
        sql(cfg,live,primary,"INSERT INTO public."+table+" VALUES ('included');")
        target=sql(cfg,live,primary,'SELECT clock_timestamp();');target_wal=sql(cfg,live,primary,'SELECT pg_walfile_name(pg_current_wal_insert_lsn());')
        time.sleep(2)
        sql(cfg,live,primary,"INSERT INTO public."+table+" VALUES ('excluded');")
        following_wal=sql(cfg,live,primary,'SELECT pg_walfile_name(pg_current_wal_insert_lsn());')
        sql(cfg,live,primary,'SELECT pg_switch_wal();')
        record.update(recovery_target=target,required_wal_segments=sorted({target_wal,following_wal}));save()
        private=yaml.safe_load((args.recovery_dir/'recovery.yaml').read_text())['database_backups']
        s3=boto3.client('s3',endpoint_url=private['endpoint'],region_name='auto',aws_access_key_id=private['access_key_id'],
            aws_secret_access_key=private['secret_access_key'],config=Config(connect_timeout=10,read_timeout=20,retries={'max_attempts':0}))
        started=time.monotonic()
        for _ in range(120):
            keys=[]
            for wal in record['required_wal_segments']:
                prefix=env+'/liora-'+env+'/wals/'+wal[:16]+'/'+wal
                response=s3.list_objects_v2(Bucket='liora-backup',Prefix=prefix)
                keys.extend(x['Key'] for x in response.get('Contents',[]) if x['Key'].endswith(wal+'.lz4'))
            if len(keys)==len(record['required_wal_segments']):break
            time.sleep(2)
        else:raise RuntimeError('Target/following WAL upload not confirmed')
        record['forced_switch_to_archived_seconds']=round(time.monotonic()-started,3);record['wal_objects']=keys
        # The conservative RTO clock includes marker/archive setup, not infrastructure rebuild.
        record['setup_seconds']=round(time.monotonic()-began,3);record['restore_started_at']=dt.datetime.now(dt.timezone.utc).isoformat();save()
        ns=record['namespace'];created=create(cfg,{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'liora.aprt.info/pitr-run':run_id}}})
        record['namespace_uid']=created['metadata']['uid'];save()
        for name in ['r2-backup','cnpg-app','cnpg-superuser','backend-secrets','ghcr-pull-secret']:
            secret=kube(cfg,['-n',live,'get','secret',name,'-o','json']);secret['metadata']={'name':name,'namespace':ns};create(cfg,secret)
        original_store=kube(cfg,['-n',live,'get','objectstore','r2-backup','-o','json'])
        cluster,store=make_restore(source,original_store,ns,backup_id,target,env)
        (directory/'restore-cluster.json').write_text(json.dumps(cluster,indent=2))
        create(cfg,store);create(cfg,cluster)
        for _ in range(600):
            restored=kube(cfg,['-n',ns,'get','cluster','pitr-db','-o','json'])
            if restored.get('status',{}).get('readyInstances')==1 and any(c['type']=='Ready' and c['status']=='True' for c in restored['status'].get('conditions',[])):break
            time.sleep(2)
        else:raise RuntimeError('PITR database readiness timeout')
        record['database_ready_seconds']=round(time.monotonic()-began,3);primary=restored['status']['currentPrimary']
        contents=sql(cfg,ns,primary,'SELECT json_agg(name ORDER BY name) FROM public.'+table+';');assert json.loads(contents)==['included']
        state=json.loads(sql(cfg,ns,primary,"SELECT json_build_object('owner',(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='app'),'migration',(SELECT version_num FROM alembic_version),'recovery',pg_is_in_recovery(),'version',current_setting('server_version'),'user_table_owner',(SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='user'),'item_table_owner',(SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='item'),'extensions',(SELECT json_agg(extname) FROM pg_extension));"))
        expected=sql(cfg,live,source['status']['currentPrimary'],'SELECT version_num FROM alembic_version;')
        assert state['owner']==state['user_table_owner']==state['item_table_owner']=='app_owner';assert state['migration']==expected;assert not state['recovery'];assert state['version'].startswith('16.15');assert 'uuid-ossp' in state['extensions']
        record.update(included_marker_present=True,excluded_marker_absent=True,restored_database=state)
        application_check(cfg,ns,live,record)
        record['application_usable_seconds']=round(time.monotonic()-began,3);record['rto_target_seconds']=3600 if env=='prod' else 14400
        record['observed_rto_within_objective']=record['application_usable_seconds']<=record['rto_target_seconds'];assert record['observed_rto_within_objective']
        assert not restored['spec'].get('plugins');assert 'retentionPolicy' not in store['spec']
        record['source_archive_write_and_cleanup_disabled']=True;record['success']=True;save()
        cleanup(cfg,record);save()
        print(json.dumps(record))
    except BaseException as error:
        record.update(error_type=type(error).__name__);save()
        raise


if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--environment',choices=['dev','stage','prod'],required=True);p.add_argument('--backup',required=True)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--recovery-dir',type=Path,default=ROOT/'recovery');args=p.parse_args()
    try:run(args)
    except BaseException as error:
        print('PITR checkpoint stopped: '+type(error).__name__+'; inspect private evidence, do not advance',file=sys.stderr);sys.exit(1)
