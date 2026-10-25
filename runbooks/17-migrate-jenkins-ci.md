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

- [ ] Configure the existing CI GitHub App with application contents/PR read and commit-status write.
- [ ] Configure `fastapi-gitops` installation access to both repositories:
  `fastapi-traefik-liora-application` and `fastapi-traefik-liora-infrastructure`.
- [ ] Require Contents read/write, Pull requests read/write and Metadata read.
- [ ] Restore the App IDs/private keys through Jenkins credential management using IDs `github-ci-app` and `gitops-app` in their respective CI/trusted scopes.
- [ ] Restore `ghcr-write` in the trusted publisher scope.
- [ ] Inspect infrastructure main rules before enabling the direct STAGE writer. Resolve a rejected write through the repository owner; do not bypass branch rules.

GitHub installation settings are external configuration. Restoring a private key
does not restore the installation's repository selection or permissions.
Never place publishing credentials on `host-ci`.

## 3. Prepare pinned agents and jobs

- [ ] For a new controller home, complete
      [fresh agent installation](22-install-fresh-jenkins-agents.md) first.

- [ ] Review the controller, agent images and resource settings under [Jenkins manifests](../kubernetes/platform/nonprod/jenkins/).
- [ ] Prepare matching immutable trusted helper bundles from the helper's pinned application revision:

```sh
mkdir -p .local-work/jenkins
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py --output .local-work/jenkins/publisher-source.json
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py --observer --output .local-work/jenkins/observer-source.json
```

Standalone script: [prepare-jenkins-publisher-source.py](../scripts/kubernetes/prepare-jenkins-publisher-source.py).

- [ ] Match bundle names to the publisher/observer volume references before installation.
- [ ] Configure the three inbound nodes with one executor each and their matching labels.
- [ ] Provision each agent's connection Secret privately; keep registry-write and GitOps credentials in Jenkins trusted scope.
- [ ] Review the selected controller configuration and PVC before applying
      agent manifests.
- [ ] Install job definitions from the reviewed application revision: multibranch `app-ci`, manual `dev-build` and trusted `trusted/publish`.
- [ ] Validate the Declarative definitions before saving; approve only the reviewed publisher's required signatures/scripts.
- [ ] Leave jobs and triggers disabled until all agent connections and credential scopes are correct.

**Stop:** If the selected manifests require a different home, missing required home files, missing credentials or different helper revision, stop before applying them. Preserve the existing home and resolve the configuration mismatch.

## 4. Activate delivery

- [ ] Review the job allowlist and schedules for the change window.
- [ ] Run one controlled main CI and trusted publication; inspect both build results.
- [ ] Require STAGE acceptance for the exact application SHA and frontend/backend digest pair.
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

## 6. Controller backup and recovery checklist

For recovery, use [the controller restore runbook](23-restore-jenkins-controller.md)
with this artifact inventory.

- [ ] Block new builds and promotions; drain active work.
- [ ] Stop the controller before taking the final home copy.
- [ ] Preserve the complete home, including users, jobs/builds/artifacts, plugins, credentials, `secrets/master.key`, `secrets/hudson.util.Secret` and other files under `secrets/`.
- [ ] Preserve mounted JCasC/configuration, initialization hooks, image/plugin pins, agent configuration and private external credentials alongside the home archive.
- [ ] Record archive checksum, controller/plugin versions, PVC/PV identity and the stopped-copy timestamp.
- [ ] Store the archive and private recovery configuration off-host. Keep the original immutable during restoration.
- [ ] Restore to separately identified empty storage with Jenkins stopped. Match its filesystem ownership and mounted configuration to the saved deployment.
- [ ] Start under an execution hold; verify decryption, administrator login, retained users/history, agent identities and job definitions before allowing work.
- [ ] Restore only the approved job/trigger settings after a controlled delivery check.

Docker build cache and agent workspaces are disposable; they are not substitutes
for controller state. Database R2 backups do not include the Jenkins home.
Use the [disaster recovery inventory](../01-Disaster_recovery.md#2-select-recovery-artifacts) to identify the controller archive and its matching deployment configuration.

## Failure response

- [ ] On CI or publication failure, retain native build results and artifacts; inspect the failed stage.
- [ ] On acceptance failure, keep PROD blocked and inspect Argo, ready running image IDs and the STAGE URL route.
- [ ] Do not replace a failed acceptance record with a passing status manually.
- [ ] Do not reset the administrator, delete build history, overwrite a home or rerun a publisher against an unknown candidate.
- [ ] Roll back application versions through a reviewed Git change; retain database compatibility checks.

**Done when:** Administrator access, controller state and agent separation are intact; only approved jobs run; the selected delivery cycle has successful CI, publication and source/digest-bound STAGE acceptance.
