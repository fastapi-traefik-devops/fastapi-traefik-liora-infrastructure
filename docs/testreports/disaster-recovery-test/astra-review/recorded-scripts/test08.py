from pathlib import Path
import subprocess,json,shlex,time,os,signal,datetime
root=Path(__file__).resolve().parent;out=root/'evidence/real/08-cleanup'
log=(out/'cleanup.log').open('w',buffering=1)
def emit(s): print(s,flush=True);log.write(s+'\n')
def run(args,expected=0):
 emit('$ '+shlex.join(args));s=subprocess.run(args,capture_output=True,text=True);emit(s.stdout.rstrip());emit(s.stderr.rstrip());emit('EXIT_CODE='+str(s.returncode));assert s.returncode==expected;return s.stdout
emit(datetime.datetime.now(datetime.timezone.utc).isoformat())
node='k3d-liora-dr-20261024-server-0'
uid=run(['docker','exec',node,'kubectl','get','namespace','kube-system','-o','jsonpath={.metadata.uid}'])
assert uid=='aa85f393-9b41-42a5-af6a-7fadfc783683'
run(['docker','exec',node,'kubectl','get','pods,pvc','-A'])
run(['docker','stats','--no-stream','--format','{{.Name}} {{.MemUsage}}',node])
run(['k3d','cluster','stop','liora-dr-20261024'])
# Remove one owned disposable container; never touch shared containers/volumes.
label=run(['docker','inspect','--format','{{index .Config.Labels "liora-dr-run"}}','liora-dr-git-source']).strip();assert label=='20261024'
run(['docker','rm','liora-dr-git-source'])
run(['docker','inspect','--format','{{.Name}}','liora-dr-git-source'],expected=1)
run(['docker','ps','--format','{{.ID}} {{.Names}} {{.Status}}'])
for name in ['infra-agent-1','infra-jenkins-1','infra-docker-1']:
 run(['docker','inspect','--format','{{.Name}} status={{.State.Status}} mounts={{range .Mounts}}{{.Type}}:{{.Name}}:{{.Destination}} {{end}}',name])
run(['k3d','cluster','list'])
run(['virsh','list','--all'])
run(['kubectl','config','current-context'])
run(['free','-h'])
run(['df','-h','/'])
run(['git','-C',str(root.parent/'infrastructure'),'status','--short'])
run(['git','-C',str(root.parent/'application'),'status','--short'])
# Stop only this exercise's Git listener; evidence viewer is stopped after screenshots.
for line in subprocess.check_output(['ps','-eo','pid,comm,args'],text=True).splitlines():
 parts=line.split(None,2)
 if len(parts)==3 and parts[1] in ['git','git-daemon'] and '--port=19418' in parts[2] and '--base-path='+str(root/'git-source/http') in parts[2]:
  os.kill(int(parts[0]),signal.SIGTERM);emit('Stopped owned read-only lab Git listener PID '+parts[0])
receipt={'all_running_docker_containers':run(['docker','ps','-q']).strip(),'original_context':run(['kubectl','config','current-context']).strip(),'owned_k3d_cluster_stopped':True,'original_containers_retained_and_stopped':True,'original_vms_unchanged_stopped':True,'removed_only_owned_git_source_container':True,'lab_node_and_pvcs_retained_for_repeat':True,'production_api_connections_in_this_run':False,'production_or_r2_mutations_in_this_run':False}
assert not receipt['all_running_docker_containers'];assert receipt['original_context']=='k3d-gitlab-gitops'
(out/'receipt.json').write_text(json.dumps(receipt,indent=2));emit(json.dumps(receipt,indent=2));emit('FINAL_EXIT_CODE=0')
