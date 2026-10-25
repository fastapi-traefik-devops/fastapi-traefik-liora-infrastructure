import importlib.util
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('pitr',Path(__file__).resolve().parents[1]/'pitr.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class SafetyTest(unittest.TestCase):
    def test_restore_has_no_archive_writer_retention_or_source_tracking(self):
        source={'spec':{'imageName':'postgres@sha256:fixture','storage':{'size':'2Gi'},'resources':{},'postgresql':{'parameters':{}},'plugins':[{'name':'barman-cloud.cloudnative-pg.io','isWALArchiver':True,'parameters':{'serverName':'liora-prod-recovered','barmanObjectName':'live'}}]}}
        store={'apiVersion':'barmancloud.cnpg.io/v1','kind':'ObjectStore','metadata':{'name':'live','annotations':{'argocd.argoproj.io/tracking-id':'live'}},'spec':{'retentionPolicy':'14d','configuration':{'destinationPath':'s3://fixture/prod/'}}}
        cluster,restore=p.make_restore(source,store,'pitr-prod-1234abcd','fixture-backup','2026-10-23T00:00:00Z','prod')
        self.assertEqual(cluster['spec']['externalClusters'][0]['plugin']['parameters']['serverName'],'liora-prod-recovered');self.assertEqual(cluster['spec']['instances'],1);self.assertNotIn('plugins',cluster['spec']);self.assertNotIn('retentionPolicy',restore['spec']);self.assertNotIn('annotations',restore['metadata']);self.assertEqual(store['spec']['retentionPolicy'],'14d');self.assertEqual(cluster['spec']['bootstrap']['recovery']['recoveryTarget']['backupID'],'fixture-backup')
    def test_cleanup_requires_exact_namespace_uid_and_run_identity(self):
        r={'environment':'dev','namespace':'pitr-dev-1234abcd','namespace_uid':'uid-one','run_id':'run-one','marker_table':'pitr_probe_123456abcdef'}
        ns={'metadata':{'name':r['namespace'],'uid':'uid-one','labels':{'liora.aprt.info/pitr-run':'run-one'}}}
        p.cleanup_guard(r,ns)
        for key,value in [('name','app-dev'),('uid','uid-other')]:
            original=ns['metadata'][key];ns['metadata'][key]=value
            with self.assertRaises(AssertionError):p.cleanup_guard(r,ns)
            ns['metadata'][key]=original
        ns['metadata']['labels']['liora.aprt.info/pitr-run']='another-run'
        with self.assertRaises(AssertionError):p.cleanup_guard(r,ns)


if __name__=='__main__':unittest.main()
