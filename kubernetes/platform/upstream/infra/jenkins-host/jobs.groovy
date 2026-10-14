// Reviewed local pipeline definitions; only administrators can configure/replay.
folder('app-ci')
pipelineJob('app-ci/main') {
  description('Docker CI: lint, unit/API/E2E tests, dependency/image/secret gates, immutable GHCR artifacts. No deployment.')
  disabled(false)
  // Declared here as well as in the Jenkinsfile: Job DSL regenerates this job on every
  // controller start, and the Jenkinsfile trigger only returns after the next run.
  properties {
    pipelineTriggers {
      triggers {
        pollSCM { scmpoll_spec('H/2 * * * *') }
      }
    }
  }
  definition { cps { script(new File('/opt/phase1-bootstrap/Jenkinsfile').text); sandbox() } }
}

// Job DSL regenerates this folder on every controller start, which drops credentials added
// in the UI. Define the registry credential here from controller-only Docker secrets so it
// stays scoped to the trusted folder and survives recreation. Values never enter Git or logs.
def secret = { String name -> new File("/run/secrets/${name}").text.trim() }
folder('trusted') {
  properties {
    folderCredentialsProperty {
      domainCredentials {
        domainCredentials {
          domain {
            name('')
            description('')
          }
          credentials {
            usernamePassword {
              scope('GLOBAL')
              id('ghcr-write')
              description('GHCR package-write token for trusted/publish only')
              username(secret('ghcr-write-username'))
              password(secret('ghcr-write-token'))
            }
          }
        }
      }
    }
  }
}
pipelineJob('trusted/publish') {
  description('Registry-only publisher on a separate Docker agent. Requires trusted-folder credential ghcr-write; no Git or Kubernetes access.')
  disabled(false)
  definition { cps { script(new File('/opt/phase1-bootstrap/Jenkinsfile.publish').text); sandbox(false) } }
}
