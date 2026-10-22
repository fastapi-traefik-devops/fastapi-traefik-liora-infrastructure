# Migrate the existing Jenkins CI to NONPROD K3s

**Where:** Original infrastructure checkout and read-only application source.

> [!IMPORTANT]
> **Phase 9 authorization update, 2026-10-22:** the operator approved existing
> DinD, preserving state except the legacy admin login, recreating the cache,
> migrating pipeline/settings sources without behavior changes, and immediate
> stopping of the local legacy kind/Jenkins stack. No migrated pipeline or
> promotion is authorized for automatic activation. Retain the current K3s admin
> credentials. Do not retire VM 100, delete containers/volumes or change NAT.

Latest checkpoint: the held state restore passed API/browser checks with the
unchanged current admin login. Agents, builds and publication remain inactive.
See the [restore evidence](../docs/testreports/PHASE9_STATE_RESTORE.md).

## 1. Inventory before mutation

> [!NOTE]
> The preserved deployment source is
> `kubernetes/platform/upstream/infra/jenkins-host/`. The application
> checkout still owns `Jenkinsfile`, `Jenkinsfile.promote`, and `ci/`.

- [ ] Inventory the running legacy controller without modifying it:

```bash
bash scripts/local-python.sh scripts/kubernetes/inventory-legacy-jenkins.py
```

[Standalone legacy inventory](../scripts/kubernetes/inventory-legacy-jenkins.py).
It writes private metadata under `.local-work/private/phase9/legacy-inventory.json`,
mode 0600. It reads job XML, controller configuration, credential IDs, mounts,
source hashes and authenticated queue/executor metadata without printing secret
values. It does not load jobs or call Jenkins mutation endpoints. A momentarily
empty queue is not evidence of a frozen/consistent Jenkins home.

- [ ] Read mounted runtime inputs inside the running controller and compare
      their hashes with the retained source. Preserve differences before
      any cutover.

> [!WARNING]
> Runtime bind mounts still refer to the former repository path. Do not
> restart or recreate old Docker containers from that missing path. Keep
> old paths as provenance, not replacement dependencies.

## 2. Preserve an online copy without claiming a cutover backup

- [ ] Run the online preservation helper:

```bash
bash scripts/local-python.sh scripts/kubernetes/backup-legacy-jenkins.py
```

[Standalone online preservation helper](../scripts/kubernetes/backup-legacy-jenkins.py).
It captures home and mounted runtime/secret inputs to timestamped mode-0700
subdirectories, with mode-0600 archives and a SHA-256 manifest. It validates
required controller configuration and encryption inputs. Nothing is restored,
paused or stopped. Tar exit 1 may indicate online changes; the manifest retains
its status. A hard tar failure or missing key fails without dumping diagnostics.

- [ ] Preserve the resulting private archive independently of the checkout
      before cleaning `.local-work/`.

> [!IMPORTANT]
> The output contains plaintext credentials. Protect it like the recovery
> kit; do not paste archive contents into reports or Git. Every online
> copy is labeled `consistent: false` and `restore_tested: false`. It
> excludes CI/publisher workspaces and the Docker build cache. It is not
> evidence that final transfer can run while jobs are active.

### Prepare an inactive copy offline

- [ ] Set `BACKUP_DIRECTORY` to the timestamped online preservation directory
      returned above, then prepare a separate copy:

```bash
bash scripts/local-python.sh scripts/kubernetes/stage-jenkins-home.py "$BACKUP_DIRECTORY"
```

[Standalone inactive-copy helper](../scripts/kubernetes/stage-jenkins-home.py).
It verifies the home archive against its source manifest, then streams a new
archive without extracting files, contacting Jenkins, or writing a PVC. The
output directory is mode 0700; archive and manifest are mode 0600. It leaves
the original archive untouched and preserves encryption keys, credential files,
user password hashes, build records, artifacts and plugins.

Only the copy changes: executable jobs and multibranch projects are disabled;
scan/timer triggers are removed; Pipeline resume is disabled; static agent
definitions, cloud definitions, queued work and old initialization scripts are
omitted. A new initialization hook requests quiet mode with zero controller
executors. The original configurations remain in the source backup. Unknown job
types, links/special entries, duplicate/unsafe paths, missing encryption keys,
and archive integrity errors fail for review instead of being silently accepted.

Exit 0 means the offline copy and manifest were written; exit 1 means validation
or processing failed; argument errors exit 2. Success and failure output exclude
credential values. A failed run may leave a private partial archive without a
completion manifest; do not use that output. Nothing is removed automatically.

> [!IMPORTANT]
> Online input produces a preview with `consistent=false`, `restore_tested=false`,
> `ready_for_cutover=false`; never use it as the final transfer. Stopped-source
> input is supported only with `--admin-config` pointing to the private current
> K3s admin XML. It produces an inactive restore candidate, retains the source's
> consistency flag and still does not claim runtime acceptance. Target JCasC must
> also be reviewed:
> the Phase 8 foundation sets its own admin password, while the old JCasC imports
> active agents and Job DSL. Neither should be applied unchanged to migrated
> users/jobs. Plugin/image initialization hooks and all external bootstrap inputs
> also need review before an isolated startup test.

The hook follows Jenkins' [initialization hook mechanism](https://www.jenkins.io/doc/book/managing/groovy-hook-scripts/).
The four-argument quiet-mode method was checked against Jenkins 2.585. The hook
is executed only on the migrated controller; the legacy controller remains stopped.

## 3. Verify GitHub App installation scope (read-only)

- [ ] Check existing installation metadata without changing App grants:

```bash
bash scripts/local-python.sh scripts/kubernetes/check-jenkins-github-access.py
```

[Standalone GitHub App access check](../scripts/kubernetes/check-jenkins-github-access.py).
It signs short-lived App JWTs in memory using controller-mounted keys and issues
GET requests for installation metadata. It never creates an installation token,
changes an App, writes a repository or sends a message. Output contains only
repository names, HTTP status and granted permissions; private metadata is mode
0600 in `.local-work/private/phase9/github-app-access.json`.

Expected boundaries:

| Identity | Required scope | Current verified result |
| --- | --- | --- |
| CI App / `github-ci-app` | Application contents/PR read and commit statuses write | Granted on application repository |
| GitOps App / `gitops-app` | Infrastructure contents write; PR write for reviewed promotion | Verified on both repositories: Contents write, Pull requests write, Metadata read |
| Trusted publisher / `ghcr-write` | Publish immutable GHCR images | Existing PoC identity preserved; fresh publish check pending |

> [!NOTE]
> HTTP 404 from the App installation endpoint means access was not
> verified; it does not prove the repository is absent. CI builds do
> not need infrastructure write or registry publishing credentials.

### Configure or recover the fastapi-gitops GitHub App

These are operator GitHub settings, not Kubernetes Secret changes. Reuse the
existing **fastapi-gitops** App; keep its App ID, existing private key and Jenkins
credential ID `gitops-app`. Repository access is configured on the installation,
while requested permissions are configured on the App itself.

1. As an App owner, open GitHub **Settings → Developer settings → GitHub Apps →
   fastapi-gitops → Permissions & events**. For an organization-owned App, start
   from the owning organization's GitHub App settings instead.
2. Set repository permissions to **Contents: Read and write**, **Pull requests:
   Read and write**, and **Metadata: Read-only** (required automatically by
   GitHub). Save the settings. No Actions, administration or organization write
   permissions are required for the planned digest-update PRs.
3. Open the organization's installed GitHub Apps settings, find **fastapi-gitops**
   and select **Configure**. Under **Repository access**, select these repositories:
   - `fastapi-traefik-devops/fastapi-traefik-liora-application`
   - `fastapi-traefik-devops/fastapi-traefik-liora-infrastructure`
4. Save repository selection and approve the installation's new permission
   request if GitHub presents one. Merely editing requested App permissions is
   not evidence that the installation has accepted them.
5. Run the read-only access helper above. Require HTTP 200 for **gitops** on both
   repositories, with `contents=write`, `pull_requests=write`, `metadata=read`.
   A repository selector alone is insufficient; record the actual granted result.
6. Keep the CI App's existing application-only contents/PR read and status write
   scope. Do not give the build identity infrastructure writes or move publishing
   keys onto the untrusted CI agent. No branch-protection bypass is needed for a
   human-reviewed promotion PR, and this App change does not authorize direct
   main-branch pushes or determine the unresolved promotion workflow.

The operator completed steps 1–4 on 2026-10-22. The read-only helper subsequently
verified both **gitops** installation grants with all three expected permissions.
No App settings were changed by the verification script. It does not prove a
future PR write or protected-branch merge will succeed; those are later controlled
workflow checks. Keep App keys in private operator inputs/Jenkins credentials,
never in the runbook, manifests or Git.


## 4. Prepare cluster adaptation before running agents

- [ ] Preserve the working `host-ci` and `registry-publisher` names/labels,
      one executor each, and zero controller executors.
- [ ] Keep existing agent/DinD image and tool locks. Review and pin trusted
      pipeline/helper source before publishing agent or daemon images.

> [!WARNING]
> Do not upgrade dependencies as a side effect of migration or execute
> trusted pipeline/helper code from an untrusted build checkout or mutable
> host bind mount.

Proposed placement, pending implementation review:

| Component | Placement | Request / limit | Storage / access |
| --- | --- | --- | --- |
| Controller | Existing `jenkins` namespace | Existing 100m/512Mi; 1 CPU/768Mi | Existing 5Gi home; assess actual expanded state size before transfer |
| CI agent | `jenkins-ci`, one Pod with DinD | Proposed 100m/192Mi; 500m/384Mi | Shared agent work volume; agent connection Secret only |
| DinD | Sidecar in CI Pod | Proposed 250m/1Gi; 1500m/2560Mi | Proposed 20Gi local-path cache and 5Gi shared work; private generated TLS client/server volumes |
| Publisher | `jenkins-publisher`, separate Pod | Proposed 100m/256Mi; 500m/512Mi | Proposed 5Gi work; no build-daemon certificates or Docker socket |

- [ ] Check node allocatable resources and existing workloads against the
      **proposed**, not yet created, PVCs and budgets.
- [ ] Review the source's privileged DinD requirement before enabling it
      in K3s. Keep service-account tokens and the host Docker socket absent.
- [ ] Define a precise network policy before activation so the publisher
      cannot reach the build TLS endpoint. Verify agent/DinD sidecar timing,
      shared path, and storage permissions.

> [!NOTE]
> Privileged DinD provides no kernel isolation from its worker VM.
> Namespaces alone do not isolate the publisher from the build endpoint.
> Preserve the logical build/publication separation without changing
> unrelated services.

- [ ] Plan to recreate the disposable build cache on the target. Do not
      copy/rebuild every layer locally or delete the old cache automatically.

> [!NOTE]
> Old DinD data was about 9.6GiB; the execution host had about 6.4GiB
> free before the preservation copy.

## 5. Review the final consistent backup and cutover procedure

### Authorized legacy stop and stopped-source preservation

The following helper is a **mutation**: run only under the recorded stop
authorization. It affects these local Docker containers only: `host-jenkins`,
`host-jenkins-agent`, `host-jenkins-publisher`, `host-jenkins-docker`, and
`fastapi-dev-control-plane`. It does not call either remote K3s API.

```bash
bash scripts/local-python.sh scripts/kubernetes/stop-legacy-ci.py --stop-active
```

[Standalone legacy stop helper](../scripts/kubernetes/stop-legacy-ci.py).

It first preserves full container metadata and **every Jenkins bind mount**
(including agent secrets and trusted publisher helpers) privately. It enters
quiet mode and records queued requests before canceling them. `--stop-active`
matches the operator's immediate-stop instruction: record in-flight executions
and stop without claiming they drained or passed. Without that flag, wait up to
ten minutes for active executors. Stop the five containers with a 120-second stop
timeout each. Retain containers, named volumes, old cache, sources and all
backups. A networkless, read-only, capability-free helper using the existing
controller image copies the stopped home; its exited container is retained too.
The script validates encryption/configuration members,
checks no running container uses the old home, and writes a hash manifest.
Stopped-home consistency is recorded only after those checks; it is not a
restore test or evidence that interrupted builds completed. A forced controller
termination cannot pass the clean-backup check. Outputs are mode 0600 under a
mode-0700 private directory.

Exit 0 means stop and backup completed; exit 1 means a failed operation or
validation. Errors omit private diagnostics. A failed run can leave the
controller quiet or some containers stopped: inspect the private records and
actual container state before retrying. Never assume it rolled back. Canceled
queue requests are recorded for review, not automatically replayed.

Rollback must first reconstruct missing original bind sources from the preserved
archives and inspect metadata. Do not issue `docker start` blindly: retained
containers still refer to paths absent from the host. No files or volumes are
deleted by this procedure. The staging helper supports separate
preview and stopped-source formats; never relabel a stopped archive as online.

### Restore to a new PVC while retaining the current admin login

Start from the working Phase 8 foundation and the completed stopped-source backup.
For fresh recovery, first bootstrap the namespace, login/pull Secrets and default
foundation overlay as in runbook 16. The default overlay remains the foundation;
the restored controller uses the separate `jenkins/held` overlay. Never apply the
foundation overlay over an accepted migrated controller as routine reconciliation.

- [ ] Set `STOPPED_BACKUP_DIRECTORY` to the private stopped-source directory:

```bash
bash scripts/local-python.sh scripts/kubernetes/restore-jenkins-state.py "$STOPPED_BACKUP_DIRECTORY"
```

[Standalone state-transfer helper](../scripts/kubernetes/restore-jenkins-state.py).

This changes **NONPROD Jenkins only**. It refuses an existing migration PVC or
an unexpected running foundation, checks the locked plugin input, saves current
admin XML privately and stages the stopped archive. It identifies legacy admin
by the XML user ID, replaces only that user's data with the current profile and
keeps the original `secrets/hudson.model.User.DIRNAMES` key. Jenkins 2.585 uses
that key for salted directory names; copying the new directory name unchanged
would not preserve the login. Non-admin users remain unchanged. A current admin
profile with user-scoped encrypted credentials requires separate review rather
than silently moving it under unrelated controller keys.

Before mutation it saves the original Deployment and an apply-ready rollback
object. It applies the held configuration/PVC/network policy, stops the foundation,
and creates a bounded transfer Pod on the foundation PVC's node. The original
PVC is mounted read-only. It writes a consistent private foundation-home backup
and restores only to new `jenkins-home-migrated`, refusing non-empty storage.
The tar mount-root entry is excluded so non-root extraction does not attempt to
change the PVC's root ownership/mode. Every restored file hash must match before
the transfer Pod exits and the held controller starts. No original files, PVCs
or legacy containers are deleted. Both new and old PVCs remain protected against
Argo pruning/deletion.

The held overlay preserves the current admin login through user files, with no
JCasC password reset or imported Job DSL. It explicitly retains local authentication
and the existing admin authorization matrix. Jobs/scans/resume stay disabled,
nodes/clouds and controller executors are zero, and the startup hook enters quiet
mode. Controller egress is denied, including DNS. A read-only init check refuses
startup on an empty or incomplete home. There are no runnable CI agents yet.

Private output is `.local-work/private/phase9/restore-<UTC>/`, mode 0700; XML,
archives, hash manifests, rollback objects and receipts are mode 0600. Exit 0
means Ready after file validation, **not** runtime acceptance; exit 1 means a
failed precondition/operation and exit 2 means invalid arguments. Errors suppress
private diagnostics. Failures leave data in place; inspect actual state and the
private receipts instead of rerunning a transfer over existing storage.

If extraction returned an error but all files may already have copied, inspect
the private context and backup first. This continuation **does not re-extract or
overwrite files**: it requires a stopped controller and matching rollback archive,
then checks every target file before allowing startup:

```bash
bash scripts/local-python.sh scripts/kubernetes/restore-jenkins-state.py --resume-verified-copy "$RESTORE_DIRECTORY"
```

[Standalone verified-copy continuation](../scripts/kubernetes/restore-jenkins-state.py).
It fails closed if any file is missing, changed or extra. Never use it to bypass
a failed integrity check. A rollout failure after the completion marker needs
inspection/rollback; this continuation is only for the still-running transfer Pod.

- [ ] Verify the restored controller with the current password:

```bash
bash scripts/local-python.sh scripts/kubernetes/verify-jenkins-migration.py "$RESTORE_DIRECTORY"
```

[Standalone runtime verifier](../scripts/kubernetes/verify-jenkins-migration.py).
It authenticates using the unchanged foundation Secret, performs a native browser
login, checks the retained admin password hash and original encryption/HMAC keys,
and inspects users, jobs, build history, plugins, disabled execution and empty
queue/nodes. A read-only administrative Groovy inspection via `scriptText` checks
credential IDs/scopes and decryption to presence booleans in the JVM; it does not
print credential values, bind credentials, save objects, schedule work or contact
GitHub/GHCR. It also checks that the baseline public-IP egress probe is blocked.
That probe supports the controller hold check; it is not a general network
penetration test. Exit 0 writes private `runtime-acceptance.json`; exit 1 fails
without printing secret-bearing errors. Success does not mean CI/promotion is active.

### Roll back to the retained K3s foundation

Keep the current migration PVC and private receipts. Set `RESTORE_DIRECTORY` to
the relevant restore receipt, then stop the migrated writer before switching:

```bash
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins scale deployment/jenkins --replicas=0
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins wait --for=delete pod -l app.kubernetes.io/name=jenkins --timeout=180s
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f "$RESTORE_DIRECTORY/rollback-deployment.json"
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=900s
```

The rollback object points to original `jenkins-home` and `jenkins-foundation`.
It retains the current login Secret and does not delete migrated data. The egress
hold remains intentionally present pending review. Verify the foundation login
and its original zero-job/zero-agent state. This rollback is prepared, not claimed
executed/tested by a successful forward restore. Resuming old Docker Jenkins is
a separate recovery operation requiring restoration of missing bind-source paths.

> [!IMPORTANT]
> Steps 1–6 below are implemented by the standalone helpers above. Steps 7–8
> remain an activation sequence for review; a successful restore does not
> authorize executing legacy promotion or changing pipeline behavior.

- [ ] Review remaining agent, smoke and pipeline activation work below; retain
      disabled jobs and the egress hold until that work is ready and reviewed.

### Transfer sequence and remaining activation

1. Back up the new foundation home as well as old controller inputs. Record both
   controller image/plugin hashes, job/build counts, users and credential scopes.
2. Quiet old Jenkins, prevent new execution, and record queue/executor states.
   The operator authorized immediate stopping, including in-flight work;
   preserve those records without claiming completed builds. An alternative
   fully drained window must verify every CI/publisher executor and queue item.
3. Stop the old controller cleanly, preserving its container, named volume and
   runtime bind mounts. Take the final consistent home archive and matching
   encryption/secret inputs from the stopped state with a verified manifest.
   Do not restart it from a missing Compose source path.
4. Stop the new foundation controller and back up its read-only home; restore
   only to a separate new PVC, preserving the original for rollback. Stage old state
   privately; preserve users, password hashes, master key, `hudson.util.Secret`,
   credentials, jobs/build records, fingerprints and required artifacts together.
5. Sanitize only the migration copy: no imported job DSL, no active agents,
   disable all jobs and scan/timer triggers, and enforce startup quiet mode before
   starting with the same plugin set. Preserve original configs in the backup.
   Keep the current K3s admin account/password and omit legacy admin account data.
   Preserve the remaining users. Identify admin's user directory from the XML
   user ID and retain the directory-name HMAC key; do not assume it is `admin`.
   Old encrypted credentials require old encryption keys; do not combine them
   with a fresh controller key or copy only credentials XML. The migrated users
   must not overwrite the current K3s admin login; verify its existing password
   and preserve other users deliberately.
6. Start the target without executable agents; verify quiet state, all job/user/
   history counts, credential IDs/scopes and private access. Do not run a job to
   prove credentials while polling/publication can still target the old repo.
7. Enable only a reviewed inert/manual smoke path, then CI gates, then trusted
   publication with adapted repository/promotion targets. Prove provenance,
   immutable digests, infrastructure overlay rendering and reviewed deployment.
8. Enable scans/schedules only at the accepted cutover; keep old jobs inactive to
   avoid duplicate publication. Retain both old home and consistent backups until
   replacement acceptance. VM100 shutdown/NAT removal remains operator work.

### Proposed rollback boundaries

> [!WARNING]
> Before target publication, preserve target state and resume the original
> stopped controller with its retained container and unchanged home/inputs.
> After publication, review completed registry/repository side effects;
> restarting old polling is not an automatic undo. Never discard build
> history or restore mismatched keys.

## 6. Resolve promotion before activation

> [!IMPORTANT]
> The old publisher writes STAGE to the former repository's main branch.
> Do not run it unchanged. Preserve the verified-artifact and trusted
> publisher boundary while adapting the target to this infrastructure
> repository.

- [ ] Agree branch triggers, digest selection/reuse, PR review, and PROD
      release behavior before enabling publisher promotion. The desired target
      is automatic reviewed STAGE PR creation after main CI/publication, followed
      by release-tag PROD promotion reusing the STAGE-verified digests. Pipeline
      behavior changes are deferred by the operator; preserve current sources
      and keep their execution disabled until that review.
- [ ] Confirm the final tested image will be reused, not rebuilt at release.
- [ ] Record each later PR, package publish, deployment, and rollback
      check in the Phase 9 report when performed.

> [!NOTE]
> Trigger and promotion details remain under discussion. DEV → STAGE →
> PROD acceptance does not authorize forcing every release through DEV
> or changing the feature-branch/manual DEV model. Preparation has not
> performed a new PR, publish, deployment, or rollback test.
