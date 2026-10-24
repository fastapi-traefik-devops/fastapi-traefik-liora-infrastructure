from pathlib import Path
import yaml,copy
root=Path(__file__).resolve().parent
objs=list(yaml.safe_load_all((root/'argocd-original.yaml').read_text()))
for o in objs:
 if o and o['kind']=='Deployment' and o['metadata']['name'] in ['argocd-dex-server','argocd-notifications-controller','argocd-applicationset-controller']:
  o['spec']['replicas']=0
 if o and o['kind']=='ConfigMap' and o['metadata']['name']=='argocd-cm':
  o.setdefault('data',{})['users.anonymous.enabled']='true'
 if o and o['kind']=='ConfigMap' and o['metadata']['name']=='argocd-rbac-cm':
  o.setdefault('data',{})['policy.default']='role:readonly'
 if o and o['kind']=='ConfigMap' and o['metadata']['name']=='argocd-cmd-params-cm':
  o.setdefault('data',{})['server.insecure']='true'
(root/'argocd-lab.yaml').write_text(yaml.safe_dump_all(objs,sort_keys=False))
# Restore actual GitOps definitions, with an explicit hold and lab-only destination.
project=yaml.safe_load(Path('infrastructure/kubernetes/gitops/argocd/nonprod/project.yaml').read_text())
project['metadata']['name']='liora-dr'; project['spec']['destinations']=[{'server':'https://kubernetes.default.svc','namespace':'dr-gitops'}]
apps=[project]
for env in ['dev','stage']:
 app=yaml.safe_load(Path(f'infrastructure/kubernetes/gitops/argocd/nonprod/app-{env}.yaml').read_text())
 app['metadata']['name']='recovered-'+env; app['metadata']['annotations']={'argocd.argoproj.io/skip-reconcile':'true'}; app['spec']['project']='liora-dr';app['spec']['destination']['namespace']='dr-gitops';app['spec']['syncPolicy']={'automated':{'enabled':False}}
 apps.append(app)
(root/'argocd-recovered-definitions.yaml').write_text(yaml.safe_dump_all(apps,sort_keys=False))
print('Prepared pinned Argo installation with optional controllers held and lab-only recovered Application definitions.')
