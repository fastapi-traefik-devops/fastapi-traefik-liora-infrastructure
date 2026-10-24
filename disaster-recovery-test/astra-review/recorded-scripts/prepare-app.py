from pathlib import Path
import yaml,secrets,copy
root=Path(__file__).resolve().parent
private=root/'private'; private.mkdir(mode=0o700,exist_ok=True)
ns='dr-application'
if (private/'app-credentials.json').exists(): raise SystemExit('Existing lab credentials retained; refusing regeneration.')
password=secrets.token_urlsafe(24); admin=secrets.token_urlsafe(24)
credentials={'db_password':password,'admin_password':admin,'admin_email':'dr-lab@example.com'}
(private/'app-credentials.json').write_text(__import__('json').dumps(credentials)); (private/'app-credentials.json').chmod(0o600)
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'lab-credentials','namespace':ns},'type':'kubernetes.io/basic-auth','stringData':{'username':'app_owner','password':password}}
backend={'apiVersion':'v1','kind':'Secret','metadata':{'name':'backend-secrets','namespace':ns},'stringData':{'PROJECT_NAME':'Liora Local DR Lab','POSTGRES_SERVER':'liora-lab-db-rw','POSTGRES_DB':'app','POSTGRES_USER':'app_owner','POSTGRES_PASSWORD':password,'FIRST_SUPERUSER':'dr-lab@example.com','FIRST_SUPERUSER_PASSWORD':admin,'SECRET_KEY':secrets.token_urlsafe(32),'ENVIRONMENT':'local','FRONTEND_HOST':'http://127.0.0.1:18080','BACKEND_CORS_ORIGINS':'http://127.0.0.1:18080'}}
(private/'app-secrets.yaml').write_text(yaml.safe_dump_all([secret,backend])); (private/'app-secrets.yaml').chmod(0o600)
cluster=yaml.safe_load(Path('infrastructure/kubernetes/apps/liora/components/cloudnative-pg/cluster.yaml').read_text())
cluster['metadata']={'name':'liora-lab-db','namespace':ns}; spec=cluster['spec']; spec.pop('superuserSecret'); spec['enableSuperuserAccess']=False; spec['bootstrap']['initdb']['secret']['name']='lab-credentials'; spec['resources']={'requests':{'cpu':'100m','memory':'256Mi'},'limits':{'cpu':'500m','memory':'512Mi'}}; spec['postgresql']['parameters']['shared_buffers']='64MB'
objs=[{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'liora-dr-run':'20261024'}}},cluster]
pins=yaml.safe_load(Path('infrastructure/kubernetes/apps/liora/overlays/dev/kustomization.yaml').read_text())['images']
for role in ['backend','frontend']:
 pin=next(p for p in pins if p['name']==role)
 obj=yaml.safe_load(Path(f'infrastructure/kubernetes/apps/liora/base/deployment-{role}.yaml').read_text())
 obj['metadata']={'name':role,'namespace':ns}; pod=obj['spec']['template']['spec'];pod.pop('imagePullSecrets',None); c=pod['containers'][0]; c['image']=pin['newName']+'@'+pin['digest'];c['resources']={'requests':{'cpu':'50m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'384Mi' if role=='backend' else '64Mi'}}
 if role=='backend':
  c['envFrom']=[{'secretRef':{'name':'backend-secrets'}}]; c['command']=['fastapi','run','--workers','1','app/main.py']
  pod['initContainers']=[{'name':'initialize-disposable-db','image':c['image'],'command':['bash','scripts/prestart.sh'],'envFrom':c['envFrom'],'resources':c['resources']}]
 objs.append(obj)
 objs.append({'apiVersion':'v1','kind':'Service','metadata':{'name':role,'namespace':ns},'spec':{'selector':{'app':role},'ports':[{'port':80,'targetPort':8000 if role=='backend' else 80}]}})
# Only DNS and namespace-local database traffic; no external services.
objs.append({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'local-only-egress','namespace':ns},'spec':{'podSelector':{'matchExpressions':[{'key':'app','operator':'In','values':['backend','frontend']}]},'policyTypes':['Egress'],'egress':[{'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':ns}}}]},{'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}}}],'ports':[{'protocol':'UDP','port':53},{'protocol':'TCP','port':53}]}]}})
(root/'app-lab.yaml').write_text(yaml.safe_dump_all(objs,sort_keys=False))
print('Prepared lab-only manifests; generated credentials stored privately, values suppressed.')
