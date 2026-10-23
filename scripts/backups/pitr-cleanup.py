#!/usr/bin/env python3
"""Explicitly clean an identified failed PITR namespace using retained UID evidence."""
import argparse
import json
import os
from pathlib import Path
from pitr import cleanup

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',required=True,type=Path);args=p.parse_args()
try:
    os.umask(0o077);record=json.loads(args.record.read_text())
    if not record.get('cleanup_complete'):
        config=Path.home()/'.kube'/('config-prod' if record['environment']=='prod' else 'config-dev-stage')
        cleanup(config,record);args.record.write_text(json.dumps(record,indent=2)+'\n');args.record.chmod(0o600)
    print('Recorded isolated resources are cleaned; source database endpoints were not changed')
except Exception as error:raise SystemExit('PITR cleanup stopped: '+type(error).__name__+'; inspect the retained identities, never force deletion')
