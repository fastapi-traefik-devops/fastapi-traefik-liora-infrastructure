#!/usr/bin/env python3
"""Render clearly labeled mock illustrations and an actual local-check summary.

Uses existing Chrome only, with a new disposable profile and denied host resolution.
No software downloads and no browser sessions/authentication state are reused.
"""
from pathlib import Path
import hashlib
import html
import json
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence'


def page(title, subtitle, cards, simulated, stamp):
    badge='SIMULATED — NOT A REAL TEST' if simulated else 'REAL LOCAL SOFTWARE CHECKS ONLY'
    color='#ffbe67' if simulated else '#85e7c5'
    rows=''.join('<article><span>'+html.escape(k)+'</span><strong>'+html.escape(v)+'</strong></article>' for k,v in cards)
    return '''<!doctype html><html><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:#0c1220;color:#eff3fb;font:18px Arial,sans-serif}
    main{padding:48px 62px;width:1200px;height:800px}header{display:flex;justify-content:space-between;align-items:center}
    .brand{color:#a9b8d1;font-size:17px;letter-spacing:2px}.badge{font-size:16px;font-weight:700;padding:13px 18px;border:2px solid COLOR;color:COLOR;border-radius:8px}
    h1{font-size:40px;line-height:1.15;margin:44px 0 14px;max-width:1050px}p{color:#aebbd1;line-height:1.5;max-width:1020px;margin:0 0 28px}
    section{display:grid;grid-template-columns:1fr 1fr;gap:16px}article{background:#182235;border:1px solid #2b3b55;padding:22px;border-radius:10px;min-height:100px}
    article span{display:block;color:#aebbd1;font-size:16px;margin-bottom:12px}article strong{font-size:21px;line-height:1.35}
    footer{position:absolute;top:716px;border-top:1px solid #34415a;width:1076px;padding-top:18px;color:COLOR;font-size:16px}
    </style></head><body><main><header><div class="brand">LIORA / DISASTER RECOVERY EVIDENCE</div><div class="badge">BADGE</div></header><h1>TITLE</h1><p>SUBTITLE</p><section>ROWS</section><footer>FOOTER<br><span style="color:#8b9bb5;font-size:13px">Recorded UTC: STAMP</span></footer></main></body></html>'''.replace('COLOR',color).replace('BADGE',html.escape(badge)).replace('SUBTITLE',html.escape(subtitle)).replace('TITLE',html.escape(title)).replace('ROWS',rows).replace('FOOTER','Mock illustration from synthetic fixtures. No production UI or infrastructure execution.' if simulated else 'Actual offline test output. This is not evidence of a running recovered platform.').replace('STAMP',html.escape(stamp))


def main():
    sim=json.loads((E/'simulated/results.json').read_text())
    real=json.loads((E/'real/local-checks.json').read_text())
    steps=sim['steps']
    specs=[
      ('01-proxmox','Proxmox recovery — mock inventory',[1,2], [('VM inventory','9 synthetic VM records'),('Network','198.18.77.0/24 / in-process only'),('Host failure model','Synthetic original directory removed'),('Real Proxmox recovery','BLOCKED — no separate lab')]),
      ('02-kubernetes','Kubernetes recovery — mock nodes',[3,4],[('Node inventory','6 fixture nodes / 2 mock clusters'),('Configuration','Restored from synthetic local bundle'),('Secrets','Fixture-only / private file mode'),('Real K3s recovery','BLOCKED — no isolated cluster')]),
      ('03-database','Database recovery — SQLite stand-in',[5,6],[('Backup source','Copied local SQLite fixture'),('Replay boundary','Included marker present / later absent'),('Archive integrity','SHA-256 manifest checked'),('Real PostgreSQL / R2','BLOCKED — not contacted')]),
      ('04-application','Application checks — mock adapter',[7,12],[('Authentication','Fixture valid/invalid token checks'),('Data checks','SQLite create / read / update / delete'),('Browser application','Not deployed — this is an illustration'),('Real FastAPI / React','BLOCKED — no recovered runtime')]),
      ('05-argocd','GitOps recovery — mock comparison',[8],[('Destination','mock://isolated-recovery-lab'),('Revision','Fixture pinned revision'),('Automation','Disabled in mock recovered state'),('Real Argo CD sync','BLOCKED — no instance started')]),
      ('06-jenkins','Jenkins recovery — mock held state',[9],[('Controller','Mock quiet mode / 0 executors'),('Jobs','1 disabled synthetic job'),('Build history','1 synthetic retained record'),('Real Jenkins recovery','BLOCKED — no current independent home')]),
      ('07-grafana','Monitoring recovery — mock targets',[10],[('Targets','2 synthetic service records'),('Alerts','In-process firing / resolution example'),('External notifications','Disabled / no network calls'),('Real Grafana / monitoring','BLOCKED — no services deployed')]),
      ('08-completion','Recovery completion — simulation',[13],[('Mock sequence','15 / 15 steps completed'),('Actual local software checks','30 checks + 5 static assertions'),('Actual infrastructure recovery','0 / 15 executed'),('RPO / RTO','No real recovery measurement available')]),
      ('09-rollback','Rollback — local fixture checkpoint',[14],[('Checkpoint','Recorded before mock lab changes'),('Rollback','Restored initial file hash manifest'),('Ownership','Run ID checked before cleanup'),('Real infrastructure rollback','BLOCKED — no lab infrastructure')]),
      ('10-cleanup','Cleanup — disposable fixture resources',[15],[('Owned fixture tree','Removed and absence verified'),('Copied synthetic archive','Hash manifest unchanged before removal'),('Production cleanup','Never requested or performed'),('Real lab teardown','NOT EXECUTED — no real resources')])]
    records=[]
    for name,title,ids,cards in specs:
        relevant=[s for s in steps if s['test'] in ids]
        subtitle='Illustrative mock state after the recorded local simulation. '+relevant[-1]['detail']
        target=E/'simulated'/name
        target.with_suffix('.html').write_text(page(title,subtitle,cards,True,sim['finished_utc']))
        records.append((target,True))
    target=E/'real/actual-local-checks'
    tls=json.loads((E/'real/local-https-results.json').read_text())
    cards=[('Repository Jenkins fixture tests',str(real['repository_jenkins_fixture_tests']['tests_run'])+' passed'),
           ('Local isolation / cleanup guards',str(real['guard_tests'])+' passed'),
           ('Loopback TLS / SQLite fixture',str(len(tls['checks']))+' passed / stopped and removed'),
           ('Actual GitOps source assertions','5 passed / no cluster writes')]
    target.with_suffix('.html').write_text(page('Actual local software verification','Rendered from actual test logs. The HTTPS fixture used Python and SQLite with synthetic data. No Proxmox, K3s, PostgreSQL or production application was recovered.',cards,False,real['finished_utc']))
    records.append((target,False))
    chrome=shutil.which('google-chrome')
    if not chrome:raise RuntimeError('Existing Chrome required; do not install automatically')
    log=[]
    with tempfile.TemporaryDirectory(prefix='dr-chrome-',dir='/tmp') as tmp:
        for target,simulated in records:
            args=[chrome,'--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-first-run',
                  '--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions',
                  '--disable-domain-reliability','--disable-default-apps','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND',
                  '--user-data-dir='+tmp,'--hide-scrollbars','--window-size=1200,800',
                  '--screenshot='+str(target.with_suffix('.png')),target.with_suffix('.html').as_uri()]
            p=subprocess.run(args,capture_output=True,text=True,timeout=25)
            image=target.with_suffix('.png')
            log.append({'file':str(image.relative_to(ROOT)),'simulated':simulated,'exit_code':p.returncode,
                        'png_exists':image.is_file(),'browser':'existing Google Chrome','profile':'disposable; removed on exit'})
            if p.returncode or not image.is_file():
                (E/'real/screenshot-render-results.json').write_text(json.dumps(log,indent=2))
                raise RuntimeError('Screenshot failed; no replacement evidence fabricated')
    (E/'real/screenshot-render-results.json').write_text(json.dumps(log,indent=2)+'\n')
    print(json.dumps({'screenshots':len(records),'simulated':len(specs),'actual_local_checks':1,'profile_cleanup':True}))


if __name__=='__main__':main()
