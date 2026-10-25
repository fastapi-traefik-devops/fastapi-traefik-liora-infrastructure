import jenkins.model.Jenkins
import hudson.util.Secret
def j=Jenkins.get()
assert Secret.fromString(new File(j.rootDir,'dr-encrypted-test.txt').text).getPlainText()=='SYNTHETIC-LOCAL-DR-MARKER'
assert j.getNumExecutors()==0
assert j.getItem('lab-disabled').isDisabled()
assert j.getItem('lab-disabled').getBuilds().size()==0
j.doQuietDown(false,0,'Local DR restored controller held',false)
println('DR_RESTORED_ENCRYPTION_CHECK=true; disabled_job_preserved=true; build_count=0; executors=0; quiet=true')
