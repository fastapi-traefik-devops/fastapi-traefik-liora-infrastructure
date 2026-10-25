# Restore the Jenkins controller home

**Where:** Management VM 200, `$HOME/fastapi-traefik-liora-infrastructure`.
**Target:** NONPROD Jenkins; private UI `http://192.168.77.16:8085`.
**Effect:** Copies a stopped-controller archive to a new PVC. Preserves the
archived administrator, credential keys, users, plugins and retained history.
The original PVC remains available. Jobs start disabled under an execution hold.

## 1. Select the source and target

- [ ] Hold surviving automation with [runbook 24](24-hold-surviving-automation.md).
- [ ] Prepare tools with [runbook 11](11-install-management-tools.md).
- [ ] Select a complete stopped-home backup from the protected recovery kit. Keep the source immutable. To create a new archive of the current controller, complete section 2 first, then return here.
- [ ] Require `home.tar.gz`, its `manifest.json`, matching controller Deployment/configuration, private credentials, and image/plugin pins. PostgreSQL and etcd backups do not contain Jenkins home files.
- [ ] Confirm the replacement controller uses the archived controller image and plugin versions. Do not upgrade during recovery.
- [ ] If the cluster has no controller, install only the foundation using [runbook 17, section 1](17-install-operate-jenkins.md#1-install-a-fresh-controller). Do not create jobs or connect agents yet.
- [ ] Set the source directory and a new target PVC name:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
umask 077
read -r -p 'Absolute stopped-home backup directory: ' JENKINS_BACKUP
read -r -p 'New target PVC name: ' JENKINS_RESTORE_PVC
test -f "$JENKINS_BACKUP/home.tar.gz"
test -f "$JENKINS_BACKUP/manifest.json"
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get deployment/jenkins,pvc
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get pvc "$JENKINS_RESTORE_PVC" --ignore-not-found -o name
```

**Expected:** The last command prints nothing. The controller has one Ready Pod.
**Stop:** Existing target PVC, mismatched images/plugins, incomplete archive,
unknown backup consistency, or insufficient node disk space. Do not delete an
existing PVC to reuse its name.

## 2. Create a current stopped-home backup when needed

Skip this section when recovering from an existing complete archive.

- [ ] In Jenkins, disable all jobs and periodic folder scans.
- [ ] Select **Manage Jenkins → Prepare for Shutdown**. Let active builds finish. Record and cancel queued requests.
- [ ] Create a new protected backup directory with the helper:

```sh
JENKINS_BACKUP="$PWD/.local-work/private/jenkins-backup-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/local-python.sh scripts/kubernetes/restore-jenkins-state.py --backup-only "$JENKINS_BACKUP"
```

Standalone script: [restore-jenkins-state.py](../scripts/kubernetes/restore-jenkins-state.py).

**Expected:** A completed manifest, full home archive, saved Deployment and
mounted ConfigMaps. The controller remains stopped. The helper mounts its home
read-only. Preserve separately the private Secrets and external App installation
settings listed in [recovery inputs](../recovery/README.md#jenkins-github-app-installation-recovery).

**If interrupted:** Keep the controller stopped. Preserve the incomplete output
and helper Pod for diagnosis. Do not label a partial archive consistent. Use a
new backup directory for the next attempt.

- [ ] Restart the original controller under its existing hold before starting section 3:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins scale deployment/jenkins --replicas=1
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=15m
```

- [ ] Confirm jobs remain disabled, login works and no work has started.
- [ ] Stage the completed backup, its configuration and other ignored state
      with [the recovery-kit capture procedure](../recovery/README.md#recovery-kit-checklist),
      then create and verify the encrypted off-host ZIP.

## 3. Restore to new storage

- [ ] Confirm the source directory and unused target name from section 1.
- [ ] Run the transfer:

```sh
bash scripts/local-python.sh scripts/kubernetes/restore-jenkins-state.py "$JENKINS_BACKUP" --target-pvc "$JENKINS_RESTORE_PVC"
```

The helper validates the archive checksum, rejects unsafe paths and links,
disables job triggers/resume, and adds the startup execution hold. It preserves
the archived administrator and encryption keys. It backs up the stopped original
home, creates a separate local-path PVC, compares every transferred file hash,
and starts the held controller only after the comparison succeeds.

**Expected:** `restored-ready` and a private receipt directory under
`.local-work/private/phase9/restore-*`. Record that exact directory:

```sh
read -r -p 'Absolute restore receipt directory printed by the helper: ' JENKINS_RESTORE_RECEIPT
test -f "$JENKINS_RESTORE_RECEIPT/transfer-context.json"
```

### Interrupted transfer

- [ ] Keep Jenkins stopped and preserve both PVCs and the transfer Pod.
- [ ] Inspect the transfer Pod's events. Do not rerun a new restore against the existing target.
- [ ] If extraction finished and only verification/start was interrupted, resume:

```sh
bash scripts/local-python.sh scripts/kubernetes/restore-jenkins-state.py --resume-verified-copy "$JENKINS_RESTORE_RECEIPT"
```

**Stop:** Hash mismatch, changed source PVC, or changed helper target. Resume
checks the recorded target and files; it does not repair a partial extraction.
Retain diagnostics and choose a separate empty PVC for another full attempt.

## 4. Accept the restored controller

- [ ] Open Jenkins and sign in with the archived administrator credentials.
- [ ] Confirm zero controller executors, quiet mode, an empty queue, disabled jobs and no active builds.
- [ ] Inspect representative retained builds and download a retained artifact.
- [ ] In **Manage Jenkins → Credentials**, confirm the expected credential IDs and scopes. Confirm there are no decryption errors in controller logs. Do not print credential values.
- [ ] Compare users, job definitions and retained build counts with the source inventory.
- [ ] Verify the selected PVC and readiness:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get deployment/jenkins -o jsonpath='{range .spec.template.spec.volumes[*]}{.name}{" "}{.persistentVolumeClaim.claimName}{"\n"}{end}'
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=15m
```

**Expected:** The `home` volume names `$JENKINS_RESTORE_PVC`.
**Stop:** Failed login, credential decryption errors, missing history or unexpected
job execution. Keep jobs held; preserve both homes and all receipts.

## 5. Reconnect or roll back

- [ ] Select the protected file containing the archived administrator password. Update only the helper authentication Secret; this does not change the Jenkins account:

```sh
read -r -p 'Absolute administrator password-file path: ' JENKINS_ADMIN_PASSWORD_FILE
test -s "$JENKINS_ADMIN_PASSWORD_FILE"
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins create secret generic jenkins-foundation-login --from-file="jenkins-admin-password=$JENKINS_ADMIN_PASSWORD_FILE" --dry-run=client -o yaml | kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins apply -f -
```

- [ ] Connect workers using [runbook 22](22-install-fresh-jenkins-agents.md).
- [ ] Keep jobs disabled until the separate activation decision in [runbook 17](17-install-operate-jenkins.md#4-activate-delivery).
- [ ] Retain the old PVC and backup helper Pods until the recovery is accepted. Delete only the specifically recorded temporary helper Pods; do not delete PVCs as routine cleanup.

If rollback is required, stop the restored controller before switching homes:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins scale deployment/jenkins --replicas=0
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins wait --for=delete pod -l app.kubernetes.io/name=jenkins --timeout=180s
```

- [ ] Restore the original mounted ConfigMap before applying the rollback Deployment:

```sh
bash scripts/local-python.sh -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); r=json.loads((p/"foundation-configmap.json").read_text()); print(json.dumps({"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":r["metadata"]["name"],"namespace":"jenkins"},"data":r["data"]}))' "$JENKINS_RESTORE_RECEIPT" | kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins apply -f -
```
- [ ] Apply the saved original Deployment:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins apply -f "$JENKINS_RESTORE_RECEIPT/rollback-deployment.json"
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=15m
```

- [ ] Recheck login and the execution hold. Preserve the failed restored PVC for diagnosis.

**Done when:** Administrator, keys, credentials and history are retained; the
selected restored home is Ready; both workers can connect; no CI, publication
or deployment was required to accept the restore.
