#!/usr/bin/env python3
"""Offline synthetic DR exercise. Never contacts infrastructure or loads real secrets.

SQLite and JSON adapters deliberately replace PostgreSQL/Kubernetes/Proxmox.
The results are simulation evidence, never infrastructure recovery PASS results.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence'
REPO = ROOT.parents[2]
INFRA = REPO if (REPO / 'kubernetes').is_dir() else REPO / 'infrastructure'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def verify(root, manifest):
    if hashes(root) != manifest:
        raise ValueError('Artifact manifest mismatch')


def remove_owned(path, owner):
    """Reject siblings, traversal, symlinks and unrecorded resource identities."""
    base = Path(owner['base']).resolve()
    original = Path(path)
    if any(p.is_symlink() for p in [original, *original.parents]):
        raise ValueError('Symlink cleanup target rejected')
    target = original.resolve()
    if target.parent != base or target.name not in owner['resources']:
        raise ValueError('Unowned cleanup target rejected')
    if (target / '.run-id').read_text() != owner['run_id']:
        raise ValueError('Run identity mismatch')
    shutil.rmtree(target)


def refuse_endpoint(endpoint):
    if endpoint != 'mock://isolated-recovery-lab':
        raise ValueError('Only the in-process mock endpoint is permitted')


def simulate():
    started = time.monotonic()
    steps = []
    run_id = str(uuid.uuid4())
    def record(number, title, detail):
        steps.append({'test': number, 'title': title, 'timestamp_utc': stamp(),
                      'real_result': 'BLOCKED', 'simulation_result': 'PASS',
                      'detail': detail, 'elapsed_local_seconds': round(time.monotonic()-started, 4)})
    # These contexts disable accidental network activity inside this simulation.
    with patch.object(socket, 'socket', side_effect=RuntimeError('Offline exercise: networking forbidden')):
        with tempfile.TemporaryDirectory(prefix='synthetic-dr-', dir=EVIDENCE / 'simulated') as tmp:
            base = Path(tmp)
            source, bundle, lab = (base / n for n in ['synthetic-original', 'copied-offsite-bundle', 'lab'])
            source.mkdir(); bundle.mkdir(); lab.mkdir()
            (lab / '.run-id').write_text(run_id)
            owner = {'base': str(base), 'run_id': run_id, 'resources': ['lab']}
            write(source / 'inventory.json', {'kind':'MOCK Proxmox', 'vms':[
                {'name':'lab-management','id':9200}, *[{'name':f'lab-k3s-{n}','id':9200+n} for n in range(1,7)],
                {'name':'lab-edge','id':9240}, {'name':'lab-router','id':9250}],
                'network':'198.18.77.0/24', 'endpoint':'mock://isolated-recovery-lab'})
            write(source / 'secrets.json', {'provenance':'SYNTHETIC ONLY', 'login_token':'fixture-token-not-a-real-credential'})
            write(source / 'argocd.json', {'destination':'mock://isolated-recovery-lab', 'revision':'fixture-pinned-revision', 'automated':False})
            write(source / 'jenkins.json', {'quiet':True,'executors':0,'jobs':[{'name':'fixture-job','disabled':True}],
                                          'builds':[{'number':1,'result':'SUCCESS','synthetic':True}], 'encryption_keys':'fixture-bytes-only'})
            write(source / 'monitoring.json', {'targets':['fixture-backend','fixture-postgres'], 'external_notifications':False})
            write(source / 'routing.json', {'host':'lab.example.invalid','backend':'mock://isolated-recovery-lab', 'tls':'mock certificate metadata only'})
            db = sqlite3.connect(source / 'base.sqlite')
            db.execute('CREATE TABLE item(id INTEGER PRIMARY KEY, title TEXT)')
            db.execute("INSERT INTO item VALUES(1,'baseline fixture')"); db.commit(); db.close()
            # Event timestamps are a synthetic clock, never measured RPO.
            write(source / 'mock-wal.json', [{'t':20,'sql':"INSERT INTO item VALUES(2,'included marker')"},
                                            {'t':40,'sql':"INSERT INTO item VALUES(3,'excluded marker')"}])
            for p in source.iterdir(): shutil.copy2(p, bundle / p.name)
            manifest = hashes(bundle)
            write(base / 'artifact-manifest.json', manifest)
            # Checkpoint and ownership inventory exist before modifying lab contents.
            checkpoint = base / 'checkpoint'
            shutil.copytree(lab, checkpoint)
            initial = hashes(lab)
            shutil.rmtree(source)
            assert not source.exists()
            record(1, 'Simulate host loss', 'Deleted only the synthetic source directory; restoration uses the copied local bundle.')
            verify(bundle, manifest)
            inventory=json.loads((bundle/'inventory.json').read_text())
            refuse_endpoint(inventory['endpoint']); write(lab/'proxmox.json', inventory)
            record(2, 'Rebuild Proxmox/network/VMs', 'Constructed nine JSON VM records on a documentation-only lab network; no hypervisor or network changes.')
            nodes=[{'name':f'fixture-node-{n}', 'ready':True, 'cluster':'nonprod' if n<4 else 'prod'} for n in range(1,7)]
            write(lab/'nodes.json', nodes); assert len(nodes)==6
            record(3, 'Recreate K3s', 'Mock adapter created two groups of three Ready node records; Terraform/Ansible/K3s were not executed.')
            shutil.copy2(bundle/'secrets.json',lab/'secrets.json'); os.chmod(lab/'secrets.json',0o600)
            assert (lab/'secrets.json').stat().st_mode & 0o777 == 0o600
            record(4, 'Recover configuration/Secrets', 'Restored fixture-only configuration with private file permissions from the independent local bundle.')
            shutil.copy2(bundle/'base.sqlite',lab/'recovered.sqlite')
            db=sqlite3.connect(lab/'recovered.sqlite')
            assert db.execute('SELECT COUNT(*) FROM item').fetchone()[0]==1
            record(5, 'Restore database backup', 'Copied and opened a real SQLite fixture; no PostgreSQL, CNPG, R2 or original cluster access.')
            for event in json.loads((bundle/'mock-wal.json').read_text()):
                if event['t']<=30: db.execute(event['sql'])
            db.commit()
            assert db.execute('SELECT id FROM item ORDER BY id').fetchall()==[(1,),(2,)]
            record(6, 'Point-in-time recovery', 'Synthetic SQL event replay to fixture time 30 includes time-20 marker and excludes time-40 marker; not PostgreSQL WAL replay.')
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            write(lab/'application.json', {'health':'ok','database_adapter':'SQLite fixture','frontend':'mock'})
            record(7, 'Restore FastAPI/React', 'In-process application adapter reads the recovered fixture; no FastAPI/React server started.')
            argo=json.loads((bundle/'argocd.json').read_text()); refuse_endpoint(argo['destination'])
            assert argo['automated'] is False
            observed=copy.deepcopy(argo);observed['revision']='fixture-drift'
            assert observed!=argo
            observed=copy.deepcopy(argo)  # explicit mock reconciliation
            assert observed==argo
            write(lab/'argocd.json',observed)
            record(8, 'Restore ArgoCD', 'Pinned fixture desired state equals observed mock state, with automation disabled; no ArgoCD instance.')
            jenkins=json.loads((bundle/'jenkins.json').read_text()); assert jenkins['quiet'] and jenkins['executors']==0
            assert all(j['disabled'] for j in jenkins['jobs']) and len(jenkins['builds'])==1
            write(lab/'jenkins.json',jenkins)
            record(9, 'Restore Jenkins', 'Preserved mock job/build records in held state; no Jenkins runtime or real credential decryption.')
            monitor=json.loads((bundle/'monitoring.json').read_text()); assert not monitor['external_notifications']
            target_up=False
            alert='firing' if not target_up else 'resolved';assert alert=='firing'
            target_up=True
            alert='firing' if not target_up else 'resolved';assert alert=='resolved'
            write(lab/'monitoring.json',monitor)
            record(10, 'Restore monitoring', 'Validated fixture target list and simulated local alert/resolution; no Prometheus/Grafana/Alertmanager services.')
            route=json.loads((bundle/'routing.json').read_text()); refuse_endpoint(route['backend'])
            assert route['host'].endswith('.invalid')
            record(11, 'Routing/HTTPS', 'Checked a mock Host/SNI mapping and synthetic TLS metadata; no HAProxy or TLS handshake.')
            token=json.loads((lab/'secrets.json').read_text())['login_token']
            def authorize(provided):
                if provided!=token: raise PermissionError('Fixture authentication rejected')
            authorize('fixture-token-not-a-real-credential')
            try: authorize('invalid')
            except PermissionError: pass
            else: raise AssertionError('Invalid token accepted')
            db.execute("INSERT INTO item VALUES(99,'CRUD fixture')");db.commit()
            assert db.execute('SELECT title FROM item WHERE id=99').fetchone()[0]=='CRUD fixture'
            db.execute("UPDATE item SET title='updated' WHERE id=99");db.commit()
            assert db.execute('SELECT title FROM item WHERE id=99').fetchone()[0]=='updated'
            db.execute('DELETE FROM item WHERE id=99');db.commit()
            assert not db.execute('SELECT * FROM item WHERE id=99').fetchall()
            db.close()
            record(12, 'Authentication/health/CRUD', 'Valid/invalid fixture token checks and actual SQLite CRUD passed; no deployed application/API tested.')
            record(13, 'RPO/RTO', 'Synthetic loss time 35 minus last recoverable event 20 gives 15 fixture units. Local elapsed time is not infrastructure RTO.')
            shutil.rmtree(lab);shutil.copytree(checkpoint,lab)
            assert hashes(lab)==initial
            record(14, 'Lab rollback', 'Filesystem lab restored exactly to the pre-change checkpoint hash manifest.')
            remove_owned(lab,owner);assert not lab.exists()
            verify(bundle,manifest)
            record(15, 'Lab cleanup', 'Only owned synthetic lab removed; copied archive hashes unchanged. TemporaryDirectory then removes this exercise fixture tree.')
            fixture_path=str(base)
        assert not Path(fixture_path).exists()
    return {'label':'SIMULATED — NOT A REAL TEST','run_id':run_id,'started_utc':steps[0]['timestamp_utc'],
            'finished_utc':stamp(),'duration_local_harness_seconds':round(time.monotonic()-started,4),
            'network_calls':0,'original_source_required':False,'fixture_tree_removed':True,
            'checkpoint_manifest':initial,'rollback_manifest':initial,
            'owned_resource_inventory':inventory,'cleanup_scope':'only the run-owned temporary fixture tree',
            'steps':steps}


class GuardTests(unittest.TestCase):
    def test_reject_live_and_unknown_endpoints(self):
        for endpoint in ['https://192.168.77.11:6443','https://192.168.77.12:6443','https://proxmox.invalid','mock://other']:
            with self.assertRaises(ValueError): refuse_endpoint(endpoint)

    def test_tampered_backup_rejected(self):
        with tempfile.TemporaryDirectory(dir=EVIDENCE/'simulated') as t:
            root=Path(t);(root/'data').write_text('fixture');m=hashes(root)
            (root/'data').write_text('altered')
            with self.assertRaises(ValueError): verify(root,m)

    def test_cleanup_rejects_sibling_and_wrong_identity(self):
        with tempfile.TemporaryDirectory(dir=EVIDENCE/'simulated') as t:
            base=Path(t);lab=base/'lab';sibling=base/'unowned';lab.mkdir();sibling.mkdir()
            (lab/'.run-id').write_text('wrong');(sibling/'keep').write_text('preserve')
            owner={'base':str(base),'run_id':'expected','resources':['lab']}
            for p in [sibling,lab,base/'..']:
                with self.assertRaises(ValueError):remove_owned(p,owner)
            assert (sibling/'keep').read_text()=='preserve'

    def test_cleanup_rejects_symlink(self):
        with tempfile.TemporaryDirectory(dir=EVIDENCE/'simulated') as t:
            base=Path(t);real=base/'real';real.mkdir();(base/'lab').symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):remove_owned(base/'lab',{'base':str(base),'run_id':'x','resources':['lab']})

    def test_network_block_is_effective(self):
        with patch.object(socket,'socket',side_effect=RuntimeError('network denied')):
            with self.assertRaises(RuntimeError):socket.socket()


def source_checks():
    import yaml
    checks=[]
    for cluster, children in [('nonprod',['app-dev','app-stage']),('prod',['app-prod'])]:
        root=INFRA/'kubernetes/gitops/argocd'/cluster
        for child in children:
            app=yaml.safe_load((root/(child+'.yaml')).read_text())
            assert app['spec']['destination']=={'server':'https://kubernetes.default.svc','namespace':child}
            auto=app['spec']['syncPolicy']['automated']
            assert auto['enabled'] and auto['selfHeal'] and auto['prune']==(cluster=='nonprod')
            checks.append({'check':child+' destination and policy','result':'PASS'})
        app=yaml.safe_load((root/'bootstrap/root.yaml').read_text())
        assert app['spec']['syncPolicy']['automated']['prune'] is False
        checks.append({'check':cluster+' root pruning disabled','result':'PASS'})
    checks.append({'check':'inventory-only: infrastructure install uses a remote upstream ArgoCD URL',
                   'result':'OBSERVED','limitation':'Complete air-gapped software bundle not supplied'})
    return checks


def repository_fixture_tests():
    """Run inspected repository tests on copies; never write into either repo."""
    with tempfile.TemporaryDirectory(prefix='repo-fixture-',dir=EVIDENCE/'real') as tmp:
        root=Path(tmp);scripts=root/'scripts/kubernetes';scripts.mkdir(parents=True)
        (root/'.local-work').mkdir()
        source=INFRA/'scripts/kubernetes'
        helper=scripts/'stage-jenkins-home.py';helper.write_bytes((source/helper.name).read_bytes())
        tests=scripts/'tests/test-stage-jenkins-home.py';tests.parent.mkdir()
        tests.write_bytes((source/'tests'/tests.name).read_bytes())
        spec=importlib.util.spec_from_file_location('jenkins_fixture_tests',tests)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        suite=unittest.defaultTestLoader.loadTestsFromModule(module)
        output=io.StringIO()
        with patch.object(socket,'socket',side_effect=RuntimeError('Offline fixture checks')):
            result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
        (EVIDENCE/'real/jenkins-fixture-tests.log').write_text(output.getvalue())
        assert result.wasSuccessful(), 'Repository fixture tests failed; inspect saved log'
        return {'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                'source_sha256':sha(source/helper.name),'copied_helper_sha256':sha(helper),
                'scope':'Actual offline archive transformations with synthetic inputs; no Jenkins runtime'}


def main():
    for name in ['real','simulated']:(EVIDENCE/name).mkdir(parents=True,exist_ok=True)
    started=stamp()
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuardTests))
    (EVIDENCE/'real/local-guard-tests.log').write_text(output.getvalue())
    assert result.wasSuccessful()
    fixture=repository_fixture_tests()
    checks=source_checks()
    simulation=simulate();write(EVIDENCE/'simulated/results.json',simulation)
    write(EVIDENCE/'real/local-checks.json',{'started_utc':started,'finished_utc':stamp(),
         'scope':'REAL LOCAL SOFTWARE CHECKS ONLY — NOT INFRASTRUCTURE RECOVERY',
         'guard_tests':result.testsRun,'repository_jenkins_fixture_tests':fixture,'static_source_checks':checks})
    print(json.dumps({'guard_tests':result.testsRun,'repository_fixture_tests':fixture['tests_run'],
                      'mock_recovery_steps':len(simulation['steps']),'fixture_cleanup_verified':simulation['fixture_tree_removed'],
                      'local_harness_seconds':simulation['duration_local_harness_seconds']}))


if __name__=='__main__':main()
