#!/usr/bin/env python3
"""Measure natural WAL delivery for a disposable marker; never switch its WAL."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

import boto3
from botocore.config import Config
import yaml
from pitr import kube, sql, ROOT


def cleanup_marker(config, namespace, primary, state):
    assert re.fullmatch('rpo_probe_[a-f0-9]{12}', state['table'])
    oid = sql(config, namespace, primary, "SELECT 'public." + state['table'] + "'::regclass::oid;")
    # PostgreSQL json_build_object encodes oid as text, while psql also returns text.
    assert int(oid) == int(state['table_oid']), 'Controlled marker identity changed'
    sql(config, namespace, primary, 'DROP TABLE public.' + state['table'] + ';')


def run(args):
    cfg=Path.home()/'.kube'/('config-prod' if args.environment=='prod' else 'config-dev-stage');ns='app-'+args.environment
    cluster=kube(cfg,['-n',ns,'get','cluster','liora-db','-o','json']);primary=cluster['status']['currentPrimary']
    if args.action=='start':
        assert not args.record.exists()
        table='rpo_probe_'+uuid.uuid4().hex[:12]
        sql(cfg,ns,primary,'CREATE TABLE public.'+table+' (id integer PRIMARY KEY);')
        # Close the PREVIOUS segment before the measured marker is committed.
        sql(cfg,ns,primary,'SELECT pg_switch_wal();')
        sql(cfg,ns,primary,'INSERT INTO public.'+table+' VALUES (1);')
        state=json.loads(sql(cfg,ns,primary,"SELECT json_build_object('acknowledged_at',clock_timestamp(),'wal',pg_walfile_name(pg_current_wal_insert_lsn()),'table_oid','public."+table+"'::regclass::oid,'archive_timeout',current_setting('archive_timeout'));"))
        state.update(environment=args.environment,table=table,archived=False,manual_switch_after_marker=False,
                     rpo_objective_seconds=900 if args.environment=='prod' else 3600)
        args.record.parent.mkdir(parents=True,exist_ok=True);args.record.write_text(json.dumps(state,indent=2));args.record.chmod(0o600);print(json.dumps(state));return
    state=json.loads(args.record.read_text());assert state['environment']==args.environment
    assert re.fullmatch('rpo_probe_[a-f0-9]{12}',state['table'])
    creds=yaml.safe_load((args.recovery_dir/'recovery.yaml').read_text())['database_backups']
    client=boto3.client('s3',endpoint_url=creds['endpoint'],region_name='auto',aws_access_key_id=creds['access_key_id'],aws_secret_access_key=creds['secret_access_key'],config=Config(connect_timeout=10,read_timeout=20,retries={'max_attempts':0}))
    committed=dt.datetime.fromisoformat(state['acknowledged_at']);deadline=committed.timestamp()+state['rpo_objective_seconds']
    while True:
        wal=state['wal'];prefix=args.environment+'/liora-'+args.environment+'/wals/'+wal[:16]+'/'+wal
        response=client.list_objects_v2(Bucket='liora-backup',Prefix=prefix)
        objects=[x for x in response.get('Contents',[]) if x['Key'].endswith(wal+'.lz4')]
        if objects:
            obj=objects[0];elapsed=(obj['LastModified']-committed).total_seconds();state.update(archived=True,wal_object=obj['Key'],archived_at=obj['LastModified'].isoformat(),observed_delivery_seconds=elapsed,observed_rpo_within_objective=0<=elapsed<=state['rpo_objective_seconds'])
            assert state['observed_rpo_within_objective']
            cleanup_marker(cfg,ns,primary,state);state['marker_cleaned']=True
            args.record.write_text(json.dumps(state,indent=2));print(json.dumps(state));return
        if time.time()>deadline:raise RuntimeError('Natural WAL delivery exceeded the environment RPO objective')
        time.sleep(10)


if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','wait']);p.add_argument('--environment',required=True,choices=['dev','stage','prod']);p.add_argument('--record',type=Path,required=True);p.add_argument('--recovery-dir',type=Path,default=ROOT/'recovery');args=p.parse_args()
    try:run(args)
    except Exception as error:raise SystemExit('RPO check stopped: '+type(error).__name__+'; preserve evidence and inspect')
