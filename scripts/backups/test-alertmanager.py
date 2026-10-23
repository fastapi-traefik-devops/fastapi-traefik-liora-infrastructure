#!/usr/bin/env python3
"""Verify Alertmanager acceptance/resolution under an exact synthetic silence.

No Slack credentials or delivery checks; no real backup alert is silenced.
"""
import datetime as dt
import json
from pathlib import Path
import urllib.request
import uuid


def main():
    results=[]
    for cluster,vip in [('nonprod','192.168.77.16'),('prod','192.168.77.17')]:
        base='http://'+vip+':9093';opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def api(path,method='GET',value=None):
            req=urllib.request.Request(base+path,method=method,data=json.dumps(value).encode() if value is not None else None,headers={'Content-Type':'application/json'})
            with opener.open(req,timeout=20) as r:
                body=r.read();return r.status,json.loads(body) if body else None
        now=dt.datetime.now(dt.timezone.utc);test=uuid.uuid4().hex
        labels={'alertname':'CNPGBackupIntegrationTest','cluster':cluster,'environment':'TEST','namespace':'monitoring','severity':'info','purpose':'test','test_id':test}
        silence={'matchers':[{'name':k,'value':labels[k],'isRegex':False,'isEqual':True} for k in ['alertname','cluster','test_id']],
            'startsAt':now.isoformat(),'endsAt':(now+dt.timedelta(minutes=5)).isoformat(),
            'createdBy':'phase10.2','comment':'Exact synthetic API-only verification; downstream notifications intentionally suppressed'}
        status,body=api('/api/v2/silences','POST',silence);assert status==200;sid=body['silenceID']
        alert={'labels':labels,'annotations':{'summary':'Synthetic backup Alertmanager API verification'},'startsAt':now.isoformat(),'endsAt':(now+dt.timedelta(minutes=3)).isoformat()}
        assert api('/api/v2/alerts','POST',[alert])[0]==200
        status,alerts=api('/api/v2/alerts');found=[a for a in alerts if a['labels'].get('test_id')==test]
        assert found and sid in found[0]['status']['silencedBy']
        alert['endsAt']=dt.datetime.now(dt.timezone.utc).isoformat();assert api('/api/v2/alerts','POST',[alert])[0]==200
        assert api('/api/v2/silence/'+sid,'DELETE')[0]==200
        prometheus=json.load(opener.open('http://'+vip+':9090/api/v1/alertmanagers',timeout=20))
        assert prometheus['data']['activeAlertmanagers']
        results.append({'cluster':cluster,'test_id':test,'synthetic_firing_accepted':True,'exact_test_silence_observed':True,'resolution_accepted':True,'test_silence_removed':True,'prometheus_alertmanager_discovery':True,'downstream_slack_tested':False})
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit('Alertmanager-only check stopped: '+type(error).__name__)
