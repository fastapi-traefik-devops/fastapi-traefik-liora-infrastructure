from pathlib import Path
import yaml,json
root=Path(__file__).resolve().parent/'monitoring'; root.mkdir(exist_ok=True)
for p in ['rules','dashboards','provisioning/dashboards','provisioning/datasources']:(root/p).mkdir(parents=True,exist_ok=True)
for p in [Path('infrastructure/kubernetes/platform/nonprod/monitoring/rules.yaml'),Path('infrastructure/kubernetes/platform/nonprod/backup-monitoring/rules.yaml')]:
 groups=[]
 for obj in yaml.safe_load_all(p.read_text()):
  if obj and obj['kind']=='PrometheusRule':groups.extend(obj['spec']['groups'])
 (root/'rules'/f'{p.parent.name}.yaml').write_text(yaml.safe_dump({'groups':groups},sort_keys=False))
for p in [Path('infrastructure/kubernetes/platform/nonprod/monitoring/dashboards.yaml'),Path('infrastructure/kubernetes/platform/nonprod/monitoring/operations-dashboard.yaml')]:
 for obj in yaml.safe_load_all(p.read_text()):
  if obj:
   for name,value in obj.get('data',{}).items():
    json.loads(value);(root/'dashboards'/name).write_text(value)
(root/'prometheus.yaml').write_text(yaml.safe_dump({'global':{'scrape_interval':'5s','evaluation_interval':'5s'},'rule_files':['/etc/prometheus/rules/*.yaml'],'scrape_configs':[{'job_name':'local-prometheus','static_configs':[{'targets':['localhost:9090']}]}]}))
(root/'alertmanager.yaml').write_text(yaml.safe_dump({'global':{'resolve_timeout':'1m'},'route':{'receiver':'discard','group_wait':'1s','group_interval':'5s','repeat_interval':'1h'},'receivers':[{'name':'discard'}]}))
(root/'provisioning/datasources/prometheus.yaml').write_text(yaml.safe_dump({'apiVersion':1,'datasources':[{'name':'Local DR Prometheus','uid':'prometheus','type':'prometheus','access':'proxy','url':'http://liora-dr-prometheus:9090','isDefault':True}]}))
(root/'provisioning/dashboards/local.yaml').write_text(yaml.safe_dump({'apiVersion':1,'providers':[{'name':'Recovered Liora definitions','folder':'Recovered repository dashboards','type':'file','options':{'path':'/var/lib/grafana/dashboards'}}]}))
(root/'dashboards/local-lab.json').write_text(json.dumps({'uid':'local-dr-runtime','title':'LOCAL DR — Real Prometheus Runtime','schemaVersion':39,'version':1,'panels':[{'id':1,'type':'stat','title':'Local scrape target UP','gridPos':{'x':0,'y':0,'w':8,'h':6},'datasource':{'type':'prometheus','uid':'prometheus'},'targets':[{'expr':'up{job="local-prometheus"}','refId':'A'}]},{'id':2,'type':'timeseries','title':'Actual Prometheus memory (bytes)','gridPos':{'x':0,'y':6,'w':24,'h':10},'datasource':{'type':'prometheus','uid':'prometheus'},'targets':[{'expr':'process_resident_memory_bytes{job="local-prometheus"}','refId':'A'}]}],'time':{'from':'now-5m','to':'now'},'refresh':'5s'}))
print('Prepared original rule groups and dashboards; notifications discarded; extra local runtime dashboard clearly labelled.')
