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
    target=directory/'test.yaml';target.write_text(yaml.safe_dump(fixture))
    subprocess.run([str(args.promtool.resolve()),'test','rules',str(target)],check=True)
