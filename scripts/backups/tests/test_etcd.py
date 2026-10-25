import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import etcd_r2
import metrics
ROOT = Path(__file__).resolve().parents[3]


class EtcdTest(unittest.TestCase):
    def test_r2_freshness_ignores_metadata_wrong_cluster_and_empty_files(self):
        client = Mock();now = dt.datetime.fromtimestamp(2000000000, dt.timezone.utc)
        def obj(key, size=10): return {'Key':key, 'Size':size, 'LastModified':now}
        client.list_objects_v2.side_effect=[{'Contents':[
            obj('etcd/nonprod/etcd-snapshot-k3s-1-01-1900000000.zip'),
            obj('etcd/nonprod/metadata/etcd-snapshot-k3s-1-02-1999999999.zip'),
            obj('etcd/prod/etcd-snapshot-k3s-1-01-1999999999.zip'),
            obj('etcd/prod/etcd-snapshot-k3s-2-01-1999999999.zip',0)],
            'IsTruncated':True,'NextContinuationToken':'next'},
            {'Contents':[obj('etcd/prod/etcd-snapshot-k3s-2-03-1950000000.zip'),obj('prod/liora-prod/base/fake',12)]}]
        size,count,latest=metrics.usage(client,'fixture',include_etcd=True)
        self.assertEqual(count,6);self.assertEqual(latest,{'nonprod':1900000000,'prod':1950000000})
        self.assertNotEqual(latest['nonprod'],now.timestamp())

    def test_no_snapshot_reports_zero_without_false_success(self):
        client=Mock();client.list_objects_v2.return_value={}
        self.assertEqual(metrics.usage(client,'fixture',include_etcd=True),(0,0,{'nonprod':0,'prod':0}))

    def test_endpoints_expose_only_selected_cluster(self):
        data={'etcd':{'nonprod':100,'prod':200}}
        self.assertIn('timestamp{cluster="nonprod"} 100',metrics.exposition(data,'nonprod'))
        self.assertNotIn('200',metrics.exposition(data,'nonprod'))

    def test_download_verifies_etcd_hash_not_only_zip_crc(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local-work') as tmp:
            path=Path(tmp)/'etcd-snapshot-k3s-1-01-1900000000.zip'
            raw=b'fixture-etcd-content'*100000
            def write(payload):
                with zipfile.ZipFile(path,'w') as z:z.writestr(path.name.removesuffix('.zip'),payload)
            write(raw+hashlib.sha256(raw).digest())
            self.assertEqual(etcd_r2.verify_snapshot(path),hashlib.sha256(path.read_bytes()).hexdigest())
            write(raw+b'x'*32)
            with self.assertRaises(ValueError):etcd_r2.verify_snapshot(path)

    def test_listing_is_prefix_scoped_and_rejects_metadata(self):
        client=Mock();now=dt.datetime.now(dt.timezone.utc)
        client.list_objects_v2.return_value={'Contents':[
            {'Key':'etcd/prod/etcd-snapshot-k3s-2-01-1900000000.zip','Size':1,'LastModified':now},
            {'Key':'etcd/prod/metadata/etcd-snapshot-k3s-2-01-1900000000.zip','Size':1,'LastModified':now}]}
        self.assertEqual(len(etcd_r2.list_snapshots(client,'liora-backup','prod')),1)
        self.assertEqual(client.list_objects_v2.call_args.kwargs['Prefix'],'etcd/prod/')
        self.assertFalse(etcd_r2.snapshot_name('nonprod','../../server.token'))

    def test_recovery_set_rejects_mismatched_token_before_copying(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local-work') as tmp:
            source=Path(tmp)/'source';output=Path(tmp)/'output';source.mkdir();output.mkdir()
            (source/'server.token').write_text('K10fixture::server:FIXTURE_ETCD_TOKEN')
            manifest={'cluster':'nonprod','cluster_uid':'fixture-uid','complete':True,'nodes':[]}
            (source/'manifest.json').write_text(json.dumps(manifest))
            metadata={'k3s-cluster-id':'fixture-uid','k3s-token-hash':'wrong'}
            with patch.object(etcd_r2.subprocess,'run',return_value=Mock(returncode=0)):
                with self.assertRaises(ValueError):etcd_r2.attach_identity(source,output,'snapshot.zip','fixture-sha',metadata,'nonprod')
                self.assertFalse((output/'server.token').exists())
                metadata['k3s-token-hash']=hashlib.sha256(b'FIXTURE_ETCD_TOKEN').hexdigest()[:12]
                etcd_r2.attach_identity(source,output,'snapshot.zip','fixture-sha',metadata,'nonprod')
            self.assertEqual(json.loads((output/'manifest.json').read_text())['snapshot_sha256'],'fixture-sha')
            self.assertEqual((output/'server.token').stat().st_mode & 0o777,0o600)

    def test_cli_explains_safe_refusals_without_external_secret_text(self):
        values={'database_backups':{'bucket':'liora-backup','endpoint':'https://fixture','region':'auto','access_key_id':'fake','secret_access_key':'fake'}}
        for error,expected in [(etcd_r2.EtcdError('Selected snapshot is absent'),'Selected snapshot is absent'),(RuntimeError('FIXTURE_SECRET_NEVER_PRINT'),'RuntimeError')]:
            with patch.object(sys,'argv',['etcd_r2.py','list','--cluster','nonprod']), patch.object(Path,'read_text',return_value=''), patch.object(etcd_r2.yaml,'safe_load',return_value=values), patch.object(etcd_r2.boto3,'client'), patch.object(etcd_r2,'list_snapshots',side_effect=error):
                with self.assertRaises(SystemExit) as stopped:etcd_r2.main()
            self.assertIn(expected,str(stopped.exception))
            self.assertNotIn('FIXTURE_SECRET_NEVER_PRINT',str(stopped.exception))

    def test_download_refuses_recovery_directory_before_writing(self):
        values={'database_backups':{'bucket':'liora-backup','endpoint':'https://fixture','region':'auto','access_key_id':'fake','secret_access_key':'fake'}}
        name='etcd-snapshot-k3s-1-01-1900000000.zip'
        target=ROOT/'recovery/fixture-etcd-download-must-not-be-created'
        argv=['etcd_r2.py','download','--cluster','nonprod','--snapshot',name,'--output',str(target)]
        with patch.object(sys,'argv',argv),patch.object(Path,'read_text',return_value=''),patch.object(etcd_r2.yaml,'safe_load',return_value=values),patch.object(etcd_r2.boto3,'client'),patch.object(etcd_r2,'list_snapshots',return_value=[{'Key':'etcd/nonprod/'+name}]):
            with self.assertRaises(SystemExit) as stopped:etcd_r2.main()
        self.assertIn('Snapshots must not be stored in recovery/',str(stopped.exception))
        self.assertFalse(target.exists())

    def test_native_rule_firing_first_error_stale_and_recovery(self):
        tool=ROOT/'.local-work/validation-tools/promtool'
        with tempfile.TemporaryDirectory(dir=ROOT/'.local-work') as tmp:
            paths=[];tests=[]
            for cluster in ['nonprod','prod']:
                value=yaml.safe_load((ROOT/f'kubernetes/platform/{cluster}/backup-monitoring/etcd-rules.yaml').read_text())
                path=Path(tmp)/(cluster+'.yaml');path.write_text(yaml.safe_dump(value['spec']));paths.append(str(path))
                rules=value['spec']['groups'][0]['rules'];failure=rules[0]['expr'];stale=rules[1]['expr']
                error='k3s_etcd_snapshot_save_s3_duration_seconds_count{job="apiserver",status="error",instance="fixture:6443"}'
                freshness='liora_etcd_r2_latest_snapshot_timestamp{cluster="'+cluster+'"}'
                tests.append({'name':cluster+': first failure and recovery','interval':'1m','input_series':[{'series':error,'values':'1x40'},{'series':freshness,'values':'1x40'}],'promql_expr_test':[
                    {'expr':failure,'eval_time':'3m','exp_samples':[{'labels':'{instance="fixture:6443"}','value':1}]},
                    {'expr':failure,'eval_time':'35m','exp_samples':[]}]})
                # First observed error must trigger even without a previous zero sample.
                tests.append({'name':cluster+': stale to fresh','interval':'1h','input_series':[{'series':freshness,'values':'1x15 57600x3'}],'promql_expr_test':[
                    {'expr':stale,'eval_time':'15h','exp_samples':[{'labels':'{}','value':53999}]},
                    {'expr':stale,'eval_time':'17h','exp_samples':[]}]})
            fixture={'rule_files':paths,'evaluation_interval':'1m','tests':tests}
            path=Path(tmp)/'tests.yaml';path.write_text(yaml.safe_dump(fixture))
            result=subprocess.run([str(tool),'test','rules',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
