// Reviewed local pipeline definitions; only administrators can configure/replay.
folder('app-ci')
pipelineJob('app-ci/main') {
  description('Docker CI: lint, unit/API/E2E tests, dependency/image/secret gates, immutable GHCR artifacts. No deployment.')
  disabled(false)
  definition { cps { script(new File('/opt/phase1-bootstrap/Jenkinsfile').text); sandbox() } }
}
folder('trusted')
pipelineJob('trusted/publish') {
  description('Registry-only publisher on a separate Docker agent. Requires trusted-folder credential ghcr-write; no Git or Kubernetes access.')
  disabled(false)
  definition { cps { script(new File('/opt/phase1-bootstrap/Jenkinsfile.publish').text); sandbox(false) } }
}
