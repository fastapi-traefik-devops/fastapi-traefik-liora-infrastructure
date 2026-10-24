import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import metrics


class MetricsTest(unittest.TestCase):
    def test_scrapes_preserve_exported_application_namespace(self):
        import yaml
        root=Path(__file__).resolve().parents[3]
        for cluster in ['nonprod','prod']:
            objects=yaml.safe_load_all((root/f'kubernetes/platform/{cluster}/backup-monitoring/monitors.yaml').read_text())
            monitor=next(x for x in objects if x['kind']=='ServiceMonitor' and x['metadata']['name']=='backup-coordinator')
            endpoint=monitor['spec']['endpoints'][0]
            self.assertTrue(endpoint['honorLabels'])
            self.assertEqual(endpoint['path'],'/metrics/'+cluster)
    def test_usage_sums_every_page(self):
        client=Mock();client.list_objects_v2.side_effect=[{'Contents':[{'Size':10},{'Size':20}],'IsTruncated':True,'NextContinuationToken':'two'},{'Contents':[{'Size':40}]}]
        self.assertEqual(metrics.usage(client,'fixture'),(70,3));self.assertEqual(client.list_objects_v2.call_args.kwargs,{'Bucket':'fixture','ContinuationToken':'two'})
    def test_bad_pagination_is_not_reported_as_full_usage(self):
        client=Mock();client.list_objects_v2.return_value={'Contents':[],'IsTruncated':True,'NextContinuationToken':'same'}
        with self.assertRaises(ValueError):metrics.usage(client,'fixture')
    def test_usage_deadline_is_bounded(self):
        with patch.object(metrics.time,'monotonic',side_effect=[0,121]):
            with self.assertRaises(TimeoutError):metrics.usage(Mock(),'fixture')
    def test_cluster_outputs_are_separate_and_contain_no_credentials(self):
        values={'success':1,'failure':0,'nonterminal':0,'ok':1}
        data={'observed':1,'environments':{e:values for e in ['dev','stage','prod']},'usage':{'bytes':100,'objects':2,'last_success':1,'ok':1},'r2_secret':'fixture-secret-never-export'}
        nonprod=metrics.exposition(data,'nonprod');prod=metrics.exposition(data,'prod')
        self.assertNotIn('PROD',nonprod);self.assertNotIn('DEV',prod);self.assertNotIn('r2_usage',prod);self.assertIn('liora_r2_usage_bytes 100',nonprod)
        self.assertNotIn(data['r2_secret'],nonprod+prod)


if __name__=='__main__':unittest.main()
