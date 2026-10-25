# Jenkins manifests

The NONPROD Jenkins controller and its two connected workers are installed from
VM 200. Use [runbook 17](../../../../runbooks/17-install-operate-jenkins.md) to
select a fresh or restored controller, [runbook 22](../../../../runbooks/22-install-fresh-jenkins-agents.md)
to connect the workers, and [runbook 27](../../../../runbooks/27-configure-jenkins-jobs.md)
for jobs and STAGE acceptance. Restore a stopped home with
[runbook 23](../../../../runbooks/23-restore-jenkins-controller.md).

The `agents/` and `initial-cycle/` overlays select a specific controller home.
Use the agent helper on a fresh or restored controller; do not apply those
overlays directly over an unreviewed PVC. Install the observer separately with
`scripts/kubernetes/deploy-jenkins-observer.py` (runbook 27, section 3).

Historical migration states and execution evidence are in
[Jenkins manifest history](../../../../docs/testreports/evidence/records/jenkins-manifest-history.md).
