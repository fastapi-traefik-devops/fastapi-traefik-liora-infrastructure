// Reviewed local job definitions; only administrators can configure/replay.
// Job DSL regenerates these items on every controller start, which drops credentials added
// in the UI. Credentials are therefore defined here from controller-only Docker secrets, each
// scoped to the folder that needs it. Values never enter Git or logs.
def secret = { String name -> new File("/run/secrets/${name}").text.trim() }
// GitHub App credentials have no DSL symbol, so Job DSL names them by class (gitHubAppCredentials)
// and expects the private key as a Secret. Without an owner, each App uses its only installation.
def org = 'fastapi-traefik-devops'
def repo = 'fastapi-traefik-liora-application'

// CI for main and pull requests. The Jenkinsfile comes from the branch, as on slide 10: a branch
// author can change it, so the CI agent holds no publishing credentials and the trusted/publish
// job stays the credentials boundary. Results are reported to GitHub as commit statuses; the
// main ruleset requires them. GitHub cannot reach this Jenkins, so it scans instead of webhooks.
multibranchPipelineJob('app-ci') {
  description('CI gates for main (release profile, then trusted publication) and pull requests (full profile). No deployment.')
  branchSources {
    branchSource {
      source {
        github {
          id('app-ci-github')
          repoOwner(org)
          repository(repo)
          repositoryUrl("https://github.com/${org}/${repo}")
          configuredByUrl(true)
          credentialsId('github-ci-app')
          traits {
            // main as a branch; pull request heads are built as PR-* instead.
            gitHubBranchDiscovery { strategyId(1) }
            // Build each pull request merged with its target, as it would land on main.
            gitHubPullRequestDiscovery { strategyId(1) }
            // Forks only from people with write access; others never run on this host.
            gitHubForkDiscovery {
              strategyId(1)
              trust { gitHubTrustPermissions() }
            }
            headWildcardFilter {
              includes('main PR-*')
              excludes('')
            }
          }
        }
      }
    }
  }
  orphanedItemStrategy {
    discardOldItems {
      numToKeep(10)
    }
  }
  triggers {
    periodicFolderTrigger { interval('2m') }
  }
  properties {
    folderCredentialsProperty {
      domainCredentials {
        domainCredentials {
          domain {
            name('')
            description('')
          }
          credentials {
            gitHubAppCredentials {
              scope('GLOBAL')
              id('github-ci-app')
              description('fastapi-ci GitHub App: read code and pull requests, write commit statuses')
              appID(secret('github-ci-app-id'))
              privateKey(hudson.util.Secret.fromString(secret('github-ci-app-key')))
            }
          }
        }
      }
    }
  }
}

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
            // GitOps promotion commits to main (stage overlay); bypasses the main ruleset.
            gitHubAppCredentials {
              scope('GLOBAL')
              id('gitops-app')
              description('fastapi-gitops GitHub App: promotion commits for trusted/publish only')
              appID(secret('github-gitops-app-id'))
              privateKey(hudson.util.Secret.fromString(secret('github-gitops-app-key')))
            }
          }
        }
      }
    }
  }
}
pipelineJob('trusted/publish') {
  description('Trusted publisher on a separate Docker agent: pushes verified SHA images to GHCR, then commits the stage promotion (credentials ghcr-write and gitops-app). No Kubernetes access.')
  disabled(false)
  definition { cps { script(new File('/opt/phase1-bootstrap/Jenkinsfile.publish').text); sandbox(false) } }
}
