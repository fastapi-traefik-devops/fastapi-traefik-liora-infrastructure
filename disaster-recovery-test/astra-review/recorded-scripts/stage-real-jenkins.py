from pathlib import Path
import runpy,tarfile,hashlib,json,os
root=Path(__file__).resolve().parent
home=root/'private/jenkins-source-home'; source=root/'private/jenkins-backup'; source.mkdir(mode=0o700,exist_ok=True)
archive=source/'home.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in home.rglob('*'):
  if p.is_file() and not p.is_symlink(): tar.add(p,arcname=str(p.relative_to(home)),recursive=False)
archive.chmod(0o600)
manifest={'mode':'stopped-preservation','consistent':True,'archives':[{'file':'home.tar.gz','bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}]}
(source/'manifest.json').write_text(json.dumps(manifest));(source/'manifest.json').chmod(0o600)
admin=next(p for p in (home/'users').rglob('config.xml') if '<id>admin</id>' in p.read_text())
admin.chmod(0o600)
helper=runpy.run_path('infrastructure/scripts/kubernetes/stage-jenkins-home.py')
staged=root/'private/jenkins-staged'; result=helper['stage'](source,staged,admin)
restored=root/'private/jenkins-restored-home'; restored.mkdir(mode=0o700,exist_ok=False)
with tarfile.open(staged/'inactive-home.tar.gz') as tar: tar.extractall(restored,filter='data')
init=restored/'init.groovy.d';init.mkdir(exist_ok=True)
(init/'99-verify.groovy').write_bytes((root/'jenkins-init/verify.groovy').read_bytes())
# Preserve immutable synthetic backup for reproduction; no private values in the public receipt.
receipt={'synthetic_lab_source':True,'source_stopped_before_archive':True,'original_helper':'infrastructure/scripts/kubernetes/stage-jenkins-home.py','helper_sha256':hashlib.sha256(Path('infrastructure/scripts/kubernetes/stage-jenkins-home.py').read_bytes()).hexdigest(),'backup_sha256':manifest['archives'][0]['sha256'],'backup_bytes':archive.stat().st_size,'source_contains_master_key':(home/'secrets/master.key').is_file(),'source_contains_hudson_util_secret':(home/'secrets/hudson.util.Secret').is_file(),'source_encrypted_marker_retained':(restored/'dr-encrypted-test.txt').read_bytes()==(home/'dr-encrypted-test.txt').read_bytes(),'master_key_preserved':(home/'secrets/master.key').read_bytes()==(restored/'secrets/master.key').read_bytes(),'hudson_secret_preserved':(home/'secrets/hudson.util.Secret').read_bytes()==(restored/'secrets/hudson.util.Secret').read_bytes(),'staged_manifest':json.loads((staged/'manifest.json').read_text())}
# Staged manifest contains hashes/counts only; remove absolute private paths for public output.
receipt.pop('staged_manifest')
(root/'evidence/real/06-jenkins/archive-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
