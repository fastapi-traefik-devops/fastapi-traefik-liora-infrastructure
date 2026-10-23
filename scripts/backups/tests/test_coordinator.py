import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('coordinator',Path(__file__).resolve().parents[1]/'coordinator.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class FakeAPI:
    def __init__(self, events, phases=None):
        self.lease={'metadata':{'name':'liora-backup-cycle','resourceVersion':'1'},'spec':{}}
        self.objects={};self.events=events;self.phases=phases or {};self.lose_post=False
    def request(self, method, path, value=None, missing=False):
        if '/leases/' in path:
            if method=='GET':return copy.deepcopy(self.lease)
            if value['metadata']['resourceVersion']!=self.lease['metadata']['resourceVersion']:raise m.UnsafeState('API conflict')
            self.lease=copy.deepcopy(value);self.lease['metadata']['resourceVersion']=str(int(self.lease['metadata']['resourceVersion'])+1);return copy.deepcopy(self.lease)
        namespace=path.split('/namespaces/')[1].split('/')[0]
        if method=='POST':
            name=value['metadata']['name'];self.events.append(namespace);self.objects[(namespace,name)]=copy.deepcopy(value)
            self.objects[(namespace,name)]['status']={'phase':self.phases.get(namespace,'completed'),'backupId':'fixture-backup'}
            if self.lose_post:raise m.UnsafeState('Lost POST response')
            return copy.deepcopy(self.objects[(namespace,name)])
        if path.endswith('/backups'):return {'items':[copy.deepcopy(v) for (ns,_),v in self.objects.items() if ns==namespace]}
        return copy.deepcopy(self.objects.get((namespace,path.rsplit('/',1)[-1])))


class CoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.events=[];self.prod=FakeAPI(self.events);self.nonprod=FakeAPI(self.events)
        self.c=m.Coordinator({'clusters':{}},apis={'prod':self.prod,'nonprod':self.nonprod},sleep=lambda _:None,clock=Mock(side_effect=range(10000)))
        self.c.alert=Mock()
    def test_order_and_no_daily_success_message(self):
        result=self.c.run();self.assertEqual(self.events,['app-prod','app-stage','app-dev']);self.assertFalse(self.prod.lease['spec']['holderIdentity']);self.assertTrue(all(s['phase']=='completed' for s in result['steps']));self.c.alert.assert_not_called()
    def test_definitive_failure_not_retried_and_advances(self):
        self.prod.phases['app-prod']='failed';self.c.run();self.assertEqual(self.events,['app-prod','app-stage','app-dev']);self.c.alert.assert_called_once_with('CNPGFullBackupFailed','prod')
    def test_running_retains_global_fence_and_blocks_following(self):
        self.prod.phases['app-prod']='running'
        with self.assertRaises(m.UnsafeState):self.c.run(timeout=1)
        self.assertEqual(self.events,['app-prod']);self.assertTrue(self.prod.lease['spec']['holderIdentity'])
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.assertEqual(self.events,['app-prod'])
    def test_lost_post_response_resume_observes_same_backup(self):
        self.prod.lose_post=True
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.prod.lose_post=False;self.c.run(resume=True)
        self.assertEqual(self.events,['app-prod','app-stage','app-dev'])
    def test_unknown_absence_is_not_recreated_after_restart(self):
        self.prod.lose_post=True
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.prod.objects.clear()
        with self.assertRaises(m.UnsafeState):self.c.run(resume=True)
        self.assertEqual(self.events,['app-prod']);self.assertTrue(self.prod.lease['spec']['holderIdentity'])
    def test_interruption_preserves_intent_and_lease(self):
        self.prod.phases['app-prod']='running';self.c.sleep=Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):self.c.run()
        self.assertEqual(self.events,['app-prod']);self.assertTrue(self.prod.lease['spec']['holderIdentity'])
        name=next(iter(self.prod.objects));self.prod.objects[name]['status']['phase']='completed';self.c.sleep=lambda _:None;self.c.run(resume=True)
        self.assertEqual(self.events,['app-prod','app-stage','app-dev'])
    def test_foreign_running_backup_blocks_acquisition(self):
        self.nonprod.objects[('app-dev','manual')]={'metadata':{'name':'manual'},'spec':{'cluster':{'name':'liora-db'}},'status':{'phase':'running'}}
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.assertFalse(self.events)
    def test_optimistic_concurrency_prevents_two_coordinators(self):
        old=self.c.lease();state={'id':'one','steps':[]};self.c.save(old,state,'one')
        with self.assertRaises(m.UnsafeState):self.c.save(old,{'id':'two','steps':[]},'two')
    def test_resume_refuses_a_fresh_active_session(self):
        self.prod.lose_post=True
        with self.assertRaises(m.UnsafeState):self.c.run()
        state=json.loads(self.prod.lease['metadata']['annotations'][m.ANNOTATION]);state.pop('blocked_at');self.prod.lease['metadata']['annotations'][m.ANNOTATION]=json.dumps(state)
        with self.assertRaises(m.UnsafeState):self.c.run(resume=True)
        self.assertEqual(self.events,['app-prod'])
    def test_fenced_old_runner_cannot_advance_or_clobber_new_owner(self):
        original=self.prod.request
        def request(method,path,value=None,missing=False):
            result=original(method,path,value,missing)
            if method=='POST':
                self.prod.lease['spec']['holderIdentity']='new-session'
                self.prod.lease['metadata']['resourceVersion']=str(int(self.prod.lease['metadata']['resourceVersion'])+1)
            return result
        self.prod.request=request
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.assertEqual(self.events,['app-prod']);self.assertEqual(self.prod.lease['spec']['holderIdentity'],'new-session')

    def test_healthy_concurrent_refusal_is_not_an_incident(self):
        self.prod.lose_post=True
        with self.assertRaises(m.UnsafeState):self.c.run()
        state=json.loads(self.prod.lease['metadata']['annotations'][m.ANNOTATION]);state.pop('blocked_at');self.prod.lease['metadata']['annotations'][m.ANNOTATION]=json.dumps(state)
        self.c.alert.reset_mock()
        with self.assertRaises(m.UnsafeState):self.c.run()
        self.c.alert.assert_not_called()

    def test_status_journal_does_not_copy_sensitive_errors(self):
        original=self.prod.request
        def request(method,path,value=None,missing=False):
            result=original(method,path,value,missing)
            if method=='GET' and result and '/backups/' in path:result['status']['error']='fixture-secret-must-not-enter-journal'
            return result
        self.prod.request=request;self.c.run();self.assertNotIn('fixture-secret',json.dumps(self.prod.lease))


if __name__=='__main__':unittest.main()
