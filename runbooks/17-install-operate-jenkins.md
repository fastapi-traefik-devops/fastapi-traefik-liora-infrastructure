# Install and operate Jenkins

**Where:** Management VM 200, infrastructure checkout; Jenkins UI through Tailscale.
**Endpoint:** `http://192.168.77.16:8085`.

## Preconditions

- [ ] Complete [private platform access](16-private-platform-access.md).
- [ ] Select NONPROD kubeconfig `$HOME/.kube/config-dev-stage`.
- [ ] Choose **fresh controller** or **restore controller state** before provisioning storage.
- [ ] Preserve existing Jenkins PVCs, administrator identity, credential encryption keys and retained history.
- [ ] Use the application checkout for `Jenkinsfile`, `Jenkinsfile.dev`, `Jenkinsfile.promote` and `ci/`.

## Configuration reference

| Component | Namespace | Purpose |
| --- | --- | --- |
| Controller | jenkins | Authentication, jobs, history; zero executors |
| `host-ci` | jenkins-ci | Application builds with Docker-in-Docker |
| `registry-publisher` | jenkins-publisher | Immutable publication and infrastructure writes |
| `stage-observer` | jenkins-acceptance | Read-only STAGE acceptance |

Build code receives neither registry-write nor infrastructure-write credentials.
Trusted publisher helpers are immutable, commit-pinned source bundles. Database
and application image deployments are separate from controller installation.

## 1. Install a fresh controller

- [ ] Confirm no accepted controller home or existing controller deployment would be replaced.
- [ ] Create login and image-pull credentials, then apply the foundation:

```sh
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod --component jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=20m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get pods,pvc
```

Standalone script: [bootstrap-platform-secrets.py](../scripts/kubernetes/bootstrap-platform-secrets.py).

- [ ] Open the private endpoint; authenticate with the protected administrator credentials.
- [ ] Confirm zero controller executors and no active jobs before configuring delivery.
- [ ] Preserve `.local-work/private/platform/nonprod-jenkins.json` in the encrypted recovery kit.

The foundation creates a new controller home. It does not populate users, job
history, credentials or agent configuration from an existing controller.
Do not apply it over a controller using an accepted restored home.

## 2. Configure delivery identities

- [ ] Confirm the GitHub App installation permissions, folder-scoped Jenkins
      credential IDs and trusted GHCR identity in
      [the job procedure](27-configure-jenkins-jobs.md#1-check-identities-and-immutable-helpers).
      Restoring a private key does not restore an App installation's repository
      selection. Keep publisher credentials out of `host-ci`.

## 3. Prepare pinned agents and jobs

- [ ] Connect `host-ci` and `registry-publisher` using
      [runbook 22](22-install-fresh-jenkins-agents.md). It preserves the
      selected controller home and leaves jobs held.
- [ ] Configure `app-ci`, `dev-build` and `trusted/publish` through
      [the one authoritative job procedure](27-configure-jenkins-jobs.md#2-configure-the-three-jobs-while-disabled).
- [ ] Prepare the STAGE observer only through
      [its separate gate](27-configure-jenkins-jobs.md#3-prepare-the-stage-observer-separately).
      A JCasC node declaration is not a running acceptance workload.

**Stop:** A different selected home, missing credentials, unreviewed helper
pin or mismatched job definition. Keep the controller quiet and preserve data.

## 4. Activate delivery

- [ ] Review the job allowlist and schedules for the change window.
- [ ] Run one controlled main CI and trusted publication; inspect both build results.
- [ ] Require automatic STAGE acceptance for the exact application SHA and
      frontend/backend digest pair. If the observer is still offline, keep
      publication held and PROD blocked; follow
      [the observer gate](27-configure-jenkins-jobs.md#3-prepare-the-stage-observer-separately).
- [ ] Confirm the infrastructure promotion commit, Argo Synced/Healthy and STAGE HTTPS.
- [ ] Enable main SCM polling at `H/2 * * * *`.
- [ ] Enable manual DEV entry only by operator request.
- [ ] Enable recurring indexing or nightly schedules only when included in the approved job policy.
- [ ] Keep PROD publication unavailable until its release-tag and exact-pair acceptance gate is approved for use.

The publisher lock spans publication, STAGE update, observation and receipt.
Superseded main builds are skipped. Preserve unrelated concurrent infrastructure
changes. PROD reuses accepted images; do not rebuild them for promotion.

## 5. Routine checks and restart

- [ ] Inspect controller and agent readiness:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get deployment,pods,pvc
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins-ci get deployment,pods,pvc
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins-publisher get deployment,pods
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins-acceptance get deployment,pods
```

- [ ] In Jenkins, inspect queue, running work, agent connectivity and the latest main/publisher results.
- [ ] Before restart, block new scheduling, drain active work and record queued requests.
- [ ] After restart, verify the administrator login, zero controller executors, agent connections and job/trigger allowlist.
- [ ] If Jenkins starts in quiet mode, release it through the UI only after those checks. Inspect recorded queued requests before requesting replacement builds.
- [ ] Recheck main polling. Do not use a helper that requests a build merely to leave quiet mode.

## 6. Preserve or restore the controller

- [ ] Create a stopped-home archive or restore an existing one with
      [runbook 23](23-restore-jenkins-controller.md). Include its matching
      Deployment, mounted configuration and protected external inputs in the
      [encrypted recovery kit](../recovery/README.md#recovery-kit-checklist).
- [ ] Preserve the old PVC, administrator, encryption keys, jobs and history.
      Keep the execution hold until the restored login and credential
      decryption pass; then use the job procedure above.

## Failure response

- [ ] On CI or publication failure, retain native build results and artifacts; inspect the failed stage.
- [ ] On acceptance failure, keep PROD blocked and inspect Argo, ready running image IDs and the STAGE URL route.
- [ ] Do not replace a failed acceptance record with a passing status manually.
- [ ] Do not reset the administrator, delete build history, overwrite a home or rerun a publisher against an unknown candidate.
- [ ] Roll back application versions through a reviewed Git change; retain database compatibility checks.

**Done when:** Administrator access, controller state and agent separation are intact; only approved jobs run; the selected delivery cycle has successful CI, publication and source/digest-bound STAGE acceptance.
