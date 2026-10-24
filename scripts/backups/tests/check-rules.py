#!/usr/bin/env python3
"""Validate native backup rule groups and firing/recovery fixtures with promtool."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import yaml

root=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--promtool',required=True,type=Path);args=p.parse_args()
with tempfile.TemporaryDirectory(dir=root/'.local-work',prefix='backup-rule-tests-') as folder:
    directory=Path(folder);files=[]
    for cluster in ['nonprod','prod']:
        value=yaml.safe_load((root/'kubernetes/platform'/cluster/'backup-monitoring/rules.yaml').read_text())
        target=directory/(cluster+'-prom-rules.yaml');target.write_text(yaml.safe_dump(value['spec']));files.append(str(target))
    subprocess.run([str(args.promtool.resolve()),'check','rules']+files,check=True)
    fixture=yaml.safe_load(Path(__file__).with_name('alert-rules.yaml').read_text());fixture['rule_files']=files
    # Exercise selectors in every environment, including actual target labels.
    for env,cluster in [('dev','nonprod'),('stage','nonprod'),('prod','prod')]:
        doc=yaml.safe_load((root/f'kubernetes/platform/{cluster}/backup-monitoring/rules.yaml').read_text())
        selected={r['alert']:r['expr'] for g in doc['spec']['groups'] for r in g['rules'] if r['labels'].get('environment')==env.upper()}
        labels=f'environment="{env.upper()}",namespace="app-{env}",job="backup-coordinator",instance="192.168.77.250:9899"'
        healthy=[{'series':f'liora_backup_telemetry_ok{{{labels}}}','values':'1x20'},
                 {'series':f'liora_backup_last_success_timestamp{{{labels}}}','values':'1000x20'},
                 {'series':f'liora_backup_last_failure_timestamp{{{labels}}}','values':'0x20'}]
        fixture['tests'].append({'name':env+': healthy ingested samples match all selectors','interval':'1m','input_series':healthy,
            'promql_expr_test':[{'expr':selected[name],'eval_time':'20m','exp_samples':[]} for name in ['CNPGBackupTelemetryMissing','CNPGFullBackupFailed','CNPGFullBackupOverdue']]})
        fixture['tests'].append({'name':env+': failed backup is detected','interval':'1m','input_series':[
            {'series':f'liora_backup_last_success_timestamp{{{labels}}}','values':'100x20'},
            {'series':f'liora_backup_last_failure_timestamp{{{labels}}}','values':'200x20'}],
            'promql_expr_test':[{'expr':selected['CNPGFullBackupFailed'],'eval_time':'20m','exp_samples':[{'labels':'{}','value':200}]}]})
        fixture['tests'].append({'name':env+': overdue backup is detected','interval':'1m','input_series':[
            {'series':f'liora_backup_last_success_timestamp{{{labels}}}','values':'1000x1800'}],
            'promql_expr_test':[{'expr':selected['CNPGFullBackupOverdue'],'eval_time':'30h','exp_samples':[{'labels':'{}','value':107000}]}]})
        fixture['tests'].append({'name':env+': missing telemetry is detected','interval':'1m','input_series':[],
            'promql_expr_test':[{'expr':selected['CNPGBackupTelemetryMissing'],'eval_time':'20m',
                'exp_samples':[{'labels':f'{{environment="{env.upper()}",namespace="app-{env}"}}','value':1}]}]})
    target=directory/'test.yaml';target.write_text(yaml.safe_dump(fixture))
    subprocess.run([str(args.promtool.resolve()),'test','rules',str(target)],check=True)
