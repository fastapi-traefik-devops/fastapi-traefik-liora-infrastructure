from pathlib import Path
import subprocess,shlex,time,json,datetime,sys
root=Path(__file__).resolve().parent
out=root/'evidence/real/07-rollback'
log=(out/'rollback.log').open('w',buffering=1)
def emit(s):print(s,flush=True);log.write(s+'\n')
def run(args,data=None,check=True):
 emit('$ '+shlex.join(args));start=time.monotonic();r=subprocess.run(args,input=data,capture_output=True)
 emit(('Captured binary pg_dump: '+str(len(r.stdout))+' bytes') if 'pg_dump' in args else r.stdout.decode(errors='replace').rstrip());emit(r.stderr.decode(errors='replace').rstrip());emit(f'EXIT_CODE={r.returncode}; elapsed_seconds={time.monotonic()-start:.3f}')
 if check and r.returncode:raise RuntimeError('Command failed; see retained log')
 return r.stdout
node='k3d-liora-dr-20261024-server-0'
def k(*args,data=None):return run(['docker','exec','-i',node,'kubectl',*args],data)
start=time.monotonic();emit(datetime.datetime.now(datetime.timezone.utc).isoformat())
try:
 uid=k('get','namespace','kube-system','-o','jsonpath={.metadata.uid}').decode()
 assert uid=='aa85f393-9b41-42a5-af6a-7fadfc783683','Unexpected cluster identity'
 # Real workload/config rollback, retaining the earlier PVC marker.
 patch={'spec':{'template':{'spec':{'containers':[{'name':'storage','image':'busybox:1.37','env':[{'name':'DR_REVISION','value':'v1'}],'command':['sh','-c','mkdir -p /www; echo "$DR_REVISION" > /www/index.html; httpd -f -p 8080 -h /www']}]}}}}
 k('-n','dr-storage','patch','deployment','persistence','--type=strategic','-p',json.dumps(patch))
 k('-n','dr-storage','scale','deployment/persistence','--replicas=1')
 k('-n','dr-storage','rollout','status','deployment/persistence','--timeout=90s')
 before=k('-n','dr-storage','exec','deployment/persistence','--','wget','-qO-','http://127.0.0.1:8080').strip();assert before==b'v1'
 marker=k('-n','dr-storage','exec','deployment/persistence','--','cat','/data/marker').strip();assert marker==b'liora-dr-20261024'
 k('-n','dr-storage','set','env','deployment/persistence','DR_REVISION=v2')
 k('-n','dr-storage','rollout','status','deployment/persistence','--timeout=90s')
 changed=k('-n','dr-storage','exec','deployment/persistence','--','wget','-qO-','http://127.0.0.1:8080').strip();assert changed==b'v2'
 rb=time.monotonic();k('-n','dr-storage','rollout','undo','deployment/persistence')
 k('-n','dr-storage','rollout','status','deployment/persistence','--timeout=90s')
 after=k('-n','dr-storage','exec','deployment/persistence','--','wget','-qO-','http://127.0.0.1:8080').strip();assert after==before
 assert k('-n','dr-storage','exec','deployment/persistence','--','cat','/data/marker').strip()==marker
 config_seconds=time.monotonic()-rb
 k('-n','dr-storage','rollout','history','deployment/persistence')
 k('-n','dr-storage','get','pods,pvc','-o','wide')
 k('-n','dr-storage','scale','deployment/persistence','--replicas=0')
 # Real PostgreSQL dump/checkpoint rollback on synthetic table only.
 k('-n','cnpg-system','scale','deployment/cnpg-controller-manager','--replicas=1')
 k('-n','cnpg-system','rollout','status','deployment/cnpg-controller-manager','--timeout=90s')
 k('-n','dr-application','annotate','cluster/liora-lab-db','cnpg.io/hibernation-')
 k('-n','dr-application','wait','--for=create','pod/liora-lab-db-1','--timeout=120s')
 k('-n','dr-application','wait','--for=condition=Ready','pod/liora-lab-db-1','--timeout=120s')
 k('-n','dr-application','wait','--for=condition=Ready','cluster/liora-lab-db','--timeout=120s')
 def sql(s):return k('-n','dr-application','exec','liora-lab-db-1','--','psql','-v','ON_ERROR_STOP=1','-U','postgres','-d','app','-Atc',s)
 sql('CREATE TABLE public.dr_checkpoint (id integer PRIMARY KEY, marker text NOT NULL); INSERT INTO public.dr_checkpoint VALUES (1, \'checkpoint-v1\');')
 baseline=sql('SELECT id,marker FROM public.dr_checkpoint ORDER BY id;')
 dump=k('-n','dr-application','exec','liora-lab-db-1','--','pg_dump','-U','postgres','-d','app','-Fc','-t','public.dr_checkpoint')
 (root/'private/local-postgres-checkpoint.dump').write_bytes(dump)
 sql("UPDATE public.dr_checkpoint SET marker='changed-v2'; INSERT INTO public.dr_checkpoint VALUES (2,'after-checkpoint');")
 changed_db=sql('SELECT id,marker FROM public.dr_checkpoint ORDER BY id;'); assert changed_db!=baseline
 dbtime=time.monotonic()
 k('-n','dr-application','exec','-i','liora-lab-db-1','--','pg_restore','-U','postgres','-d','app','--clean','--if-exists',data=dump)
 restored=sql('SELECT id,marker FROM public.dr_checkpoint ORDER BY id;');assert restored==baseline
 db_seconds=time.monotonic()-dbtime
 sql('SELECT version(); SELECT extname FROM pg_extension ORDER BY extname;')
 k('-n','dr-application','get','clusters,pods,pvc','-o','wide')
 result={'config_before':before.decode(),'config_changed':changed.decode(),'config_restored':after.decode(),'persistent_marker_preserved':True,'config_rollback_seconds':config_seconds,'postgres_baseline':baseline.decode().strip(),'postgres_changed':changed_db.decode().strip(),'postgres_restored':restored.decode().strip(),'postgres_logical_rollback_seconds':db_seconds,'total_exercise_seconds':time.monotonic()-start,'r2_restore':False,'pitr':False}
 (out/'results.json').write_text(json.dumps(result,indent=2));emit(json.dumps(result,indent=2));emit('FINAL_EXIT_CODE=0')
except Exception as e:
 emit('FAILED: '+str(e));emit('FINAL_EXIT_CODE=1');sys.exit(1)
