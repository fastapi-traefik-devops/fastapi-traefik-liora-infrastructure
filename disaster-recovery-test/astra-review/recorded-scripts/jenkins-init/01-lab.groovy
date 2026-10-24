import jenkins.model.Jenkins
import hudson.model.FreeStyleProject
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.util.Secret

def j=Jenkins.get()
j.setNumExecutors(0)
j.setSlaveAgentPort(-1)
def realm=new HudsonPrivateSecurityRealm(false)
realm.createAccount('admin',UUID.randomUUID().toString())
j.setSecurityRealm(realm)
def auth=new FullControlOnceLoggedInAuthorizationStrategy()
auth.setAllowAnonymousRead(true)
j.setAuthorizationStrategy(auth)
def p=j.getItem('lab-disabled') ?: j.createProject(FreeStyleProject.class,'lab-disabled')
p.setDescription('Disposable local recovery fixture. Never executed. No builders or triggers.')
p.disable()
p.save()
j.doQuietDown(false,0,'Local DR lab: all jobs held',false)
def f=new File(j.rootDir,'dr-encrypted-test.txt')
if(!f.exists()) f.text=Secret.fromString('SYNTHETIC-LOCAL-DR-MARKER').getEncryptedValue()
assert Secret.fromString(f.text).getPlainText()=='SYNTHETIC-LOCAL-DR-MARKER'
j.save()
println('DR_SYNTHETIC_ENCRYPTION_CHECK=true; executors=0; quiet=true; job_disabled=true')
