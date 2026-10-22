# Migrate the existing Jenkins CI to NONPROD K3s

**Where:** Original infrastructure checkout and read-only application source.

> [!IMPORTANT]
> **Phase 9 authorization update, 2026-10-22:** the operator approved existing
> DinD, preserving state except the legacy admin login, recreating the cache,
> migrating pipeline/settings sources without behavior changes, and immediate
> stopping of the local legacy kind/Jenkins stack. No migrated pipeline or
> promotion is authorized for automatic activation. Retain the current K3s admin
> credentials. Do not retire VM 100, delete containers/volumes or change NAT.

Latest checkpoint: both worker agents are online, the Docker build/bind smoke
passed, and API/browser checks again verified the unchanged current admin login.
The controller remains quiet; imported jobs and application publication remain
inactive. See the [worker evidence](../docs/testreports/PHASE9_WORKERS.md) and
[restore evidence](../docs/testreports/PHASE9_STATE_RESTORE.md).

> [!IMPORTANT]
> **Operator cleanup, 2026-10-22:** a subsequent local
> `docker system prune -a --volumes` removed the stopped legacy containers and
> local images. The seven named Jenkins volumes and private stopped-source
> archives remain; all 14 archive size/hash checks passed afterward. Both remote
> K3s clusters and their PVCs are unaffected. Inventory/online-backup/stop steps
> below describe the completed source-preservation sequence and require the
> original containers; do not rerun them against the cleaned host. For legacy
> recovery, recreate containers from the privately preserved metadata/source,
> restore missing bind inputs, and recover or rebuild images before starting.
> Never assume a removed container can be restarted. Do not prune remaining
> volumes, private archives or operator inputs during migration.
> The old kind node's anonymous data volume was also removed, confirmed against
> its preserved mount metadata. Jenkins archives do not restore that cluster's
> state. Recreating the legacy kind cluster is separate from Jenkins recovery.
> The operator confirmed that kind held only default application database data;
> no application/database transfer is required. Keep the current K3s PostgreSQL
> data without replacement or reseeding. Jenkins state is preserved separately.

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

### Educational-project vulnerability deferral

On 2026-10-22 the operator explicitly deferred vulnerability remediation and
further vulnerability scans to complete migration/deployment first. This
supersedes the image gate as a blocking condition for this educational-project
increment. It does not turn a failed scan into a pass. The recovered controller
passed; the rebuilt DinD image has High-severity `CVE-2026-111943` findings.
The agent is not rescanned after this decision. Retain the existing Dockerfiles,
tool locks and scan evidence; do not introduce dependency upgrades or new
security stages during this increment. Basic deployment, login and disabled-job
checks still apply. Remediation and a fresh complete image gate remain deferred.

The optional [standalone image audit](../scripts/kubernetes/audit-jenkins-images.py)
is available for later use; it is **not** called by the deployment helper:

```bash
bash scripts/local-python.sh scripts/kubernetes/audit-jenkins-images.py
```

[Standalone image audit](../scripts/kubernetes/audit-jenkins-images.py).
It scans sequentially with the preserved source-built scanner at
`.local-work/tools/trivy`, using a bounded 3Gi/1-CPU helper container, one scan
worker and normal vulnerability/Java database updates. It does not start Jenkins
jobs. Private timestamped JSON/logs under `.local-work/phase9/` retain scanner,
archive and report hashes. Reports must contain a complete container-image
result with filesystem layer IDs matching the inspected source image. Exit 0
requires every requested image to pass; exit 1 means a finding, scanner/export
error, missing/incomplete report or other failure; argument errors exit 2.
An OOM or empty report never counts as a pass. It removes only its own temporary
exports, preserving source images, operator inputs and recovery archives.

- [ ] Preserve the working `host-ci` and `registry-publisher` names/labels,
      one executor each, and zero controller executors.
- [ ] Keep existing agent/DinD image and tool locks. Review and pin trusted
      pipeline/helper source before publishing agent or daemon images.

> [!WARNING]
> Do not upgrade dependencies as a side effect of migration or execute
> trusted pipeline/helper code from an untrusted build checkout or mutable
> host bind mount.

Implemented worker budgets (idle observations are not application CI load tests):

| Component | Placement | Request / limit | Storage / access |
| --- | --- | --- | --- |
| Controller | Existing `jenkins` namespace | Existing 100m/512Mi; 1 CPU/768Mi | Existing 5Gi home; assess actual expanded state size before transfer |
| CI agent | `jenkins-ci`, one Pod with DinD | 100m/192Mi; 500m/384Mi | Shared 5Gi work volume; agent connection Secret only |
| DinD | Sidecar in CI Pod | 250m/1Gi; 1500m/2560Mi | Fresh 20Gi local-path cache and shared work; generated TLS volumes |
| Publisher | `jenkins-publisher`, separate Pod | 100m/256Mi; 500m/512Mi | Separate 5Gi work; no build-daemon certificates or Docker socket |

- [ ] Check node allocatable resources and existing workloads against the
      implemented PVCs and budgets before recovery/redeployment.
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

### Prepare pinned publisher helpers and worker images

The application checkout remains read-only. The helper below reads `ci/` from
Git objects at the reviewed application commit
`b98a22e48527c256193ed65c10307eb574b27ab6`, verifies the blobs and prepares an
immutable ConfigMap for `jenkins-publisher`. It does not use mutable working-tree
files, execute pipelines, or apply anything to Kubernetes. It preserves all 17
source files for the publisher's existing `/opt/phase1-ci` path.

```bash
mkdir -p .local-work/phase9
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py --output .local-work/phase9/publisher-source.json
```

[Standalone publisher-source preparation](../scripts/kubernetes/prepare-jenkins-publisher-source.py).
Exit 0 means a mode-0600 bundle was created; exit 1 means a missing/unexpected
repository, missing or changed Git object, unsupported entry or existing output;
argument errors exit 2. It never overwrites a reviewed bundle or prints source
contents/private diagnostics. Keep the reviewed commit available for recovery.

If worker images must be recovered after pruning, rebuild from the preserved
Dockerfiles and tool locks:

```bash
bash scripts/kubernetes/rebuild-jenkins-agents.sh
```

[Standalone bounded worker-image rebuild](../scripts/kubernetes/rebuild-jenkins-agents.sh).
It creates/reuses the named isolated BuildKit builder, bounded to 3Gi and 1.5 CPU
with one build step at a time, and writes logs/image IDs under
`.local-work/phase9/`. It does not change the default builder, start Jenkins
jobs, publish images, or delete existing images/volumes. Exit 0 means both
images loaded; a nonzero exit means an operation failed and partial build
cache/images may remain. Existing APK upgrade/install steps resolve current
packages, so rebuilding does not promise the former image digest. Publish with
the operator's private registry login and pin the actual resulting GHCR digests
in `jenkins/agents/workloads.yaml` before deployment. Follow the vulnerability
deferral above; do not start another scan in this increment.

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
archives and inspect metadata. After the operator cleanup, the old containers
also need recreation; `docker start` cannot restore them. No files or volumes are
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

### Deploy workers while retaining disabled jobs

Use the accepted state-restore receipt directory. This **changes NONPROD only**:

```bash
bash scripts/local-python.sh scripts/kubernetes/deploy-jenkins-agents.py "$RESTORE_DIRECTORY"
```

[Standalone worker deployment](../scripts/kubernetes/deploy-jenkins-agents.py).
The `jenkins/agents` overlay extends `held/`: the migrated home, current admin
profile, zero controller executors, startup quiet hook and controller egress hold
remain. JCasC declares only the two preserved static nodes and contains no admin
password reset or Job DSL. The helper authenticates with the current login and
requires quiet mode, disabled jobs and an empty queue before and after deployment.
It records the original controller/configuration and acceptance inputs privately,
checks pinned images, creates owned worker namespaces, server-validates manifests,
and copies only the registry pull Secret for kubelet use. It refuses an unrelated
namespace or a different pre-existing target Secret. Agent connection identities
come from authenticated JNLP metadata; values are never printed. No publisher or
App credentials are mounted into the CI Pod. The daemon has no Service or host
Docker socket; its generated TLS client certificates stay in the CI Pod.

CI and DinD share the same `/home/jenkins/agent` PVC path for nested Docker bind
mounts. The publisher has its own work PVC and immutable helper ConfigMap, without
daemon certificates. Basic network policies retain this separation: private
controller/DNS access and public HTTP(S) egress, no worker ingress. DinD remains
privileged as approved; this does not provide isolation from the worker kernel.

Private evidence is `.local-work/private/phase9/agents-<UTC>/`, mode 0700,
files 0600. Exit 0 means Deployments became ready, both agents connected and the
execution hold remained intact, **not** that a pipeline ran or promotion is
accepted. Exit 1 means a failed precondition/operation; argument errors exit 2.
A failure may leave namespaces,
PVCs or workers deployed: inspect that evidence and Kubernetes events, retain
data, and resolve the cause before retrying. No automatic rollback or deletion.

For full current-login/state checks with the two expected agents connected, set
`AGENT_EVIDENCE_DIRECTORY` to the returned private directory:

```bash
bash scripts/local-python.sh scripts/kubernetes/verify-jenkins-migration.py --connected-agents "$AGENT_EVIDENCE_DIRECTORY"
```

[Standalone runtime verification](../scripts/kubernetes/verify-jenkins-migration.py).
This mode requires both original labels, one executor each and online connections,
while checking disabled jobs, current admin API/browser login and retained state.
It never schedules a build. A successful receipt is created once; preserve it.
The earlier zero-agent acceptance remains unchanged in its original directory.

Verify the new daemon and the nested Docker bind path without scheduling any
Jenkins job or building/publishing application images:

```bash
bash scripts/local-python.sh scripts/kubernetes/smoke-jenkins-docker.py
```

[Standalone Docker/workspace smoke](../scripts/kubernetes/smoke-jenkins-docker.py).
It uses an isolated timestamped directory in the CI work PVC, resolves the small
BusyBox image to a digest, builds a trivial local image, and compares a copied
file with its read-only nested bind mount. Its test container has no network.
Success removes only that helper's image and two workspace files; failure retains
the isolated workspace for inspection. No Pipeline, credentials, application
image publication or Git write occurs. Exit 0 means build/bind checks passed;
exit 1 reports failure without printing private command diagnostics.

To return to the zero-agent held configuration, first scale `host-ci` in
`jenkins-ci` and `registry-publisher` in `jenkins-publisher` to zero, then apply
`kubernetes/platform/nonprod/jenkins/held` and restart the controller to load
its zero-node JCasC. Retain all worker PVCs, source bundles and private evidence.
Foundation rollback remains a separate procedure below.

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
a separate recovery operation requiring container recreation, available images
and restoration of missing bind-source paths after the operator cleanup.

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
> stopped controller with its retained home/inputs. After the operator cleanup,
> recreate its container and recover/rebuild its image first; the old container
> no longer exists. Restore missing bind sources from the private archives.
> After publication, review completed registry/repository side effects;
> restarting old polling is not an automatic undo. Never discard build
> history or restore mismatched keys.

## 6. Resolve promotion before activation

The [publisher/repository-split review](../docs/testreports/PHASE9_PUBLICATION_REVIEW.md)
records current blockers and the proposed local-only implementation checkpoint.
Build #2 is functional acceptance, not publication evidence. Keep jobs and
controller egress held until the separately reviewed activation steps.

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

## Manual functional-only migration checkpoint

After explicit operator agreement, use the application-owned
`Jenkinsfile.migration` and `migration` profile. Keep every imported job,
multibranch indexing, polling, schedules and trusted publisher disabled. This
checkpoint binds no write credentials, runs no security scans, produces no
release attestation/image archives and does not deploy. Do not enable the
regular `Jenkinsfile`: a manual main build can schedule publication.

Commit the reviewed application changes locally on top of the reviewed upstream
history. Do not push merely to make Jenkins fetch the source. The helper bundles
that exact commit, validates the Declarative Pipeline on Jenkins, verifies the
bundle copied to the CI work volume and installs `migration-ci` disabled.
Controller egress remains denied. All source checkout runs on `host-ci`.
The helper uses the existing `recovery/LIORA-id_ed25519` administrator SSH key
and `.local-work/phase8/node-known-hosts` to transfer the bundle into the bound
CI local-path volume. It verifies the NONPROD node, PVC binding and SHA-256;
it does not overwrite an existing bundle. Bulk `kubectl exec` stdin was observed
to truncate transfers on this lab server, so it is not used for the bundle.

```bash
bash scripts/local-python.sh scripts/kubernetes/manual-jenkins-ci.py prepare \
  "$PWD/.local-work/private/phase9/manual-ci-YYYYMMDD"
```

Review the private receipt and baseline before the one permitted activation:

```bash
bash scripts/local-python.sh scripts/kubernetes/manual-jenkins-ci.py run \
  "$PWD/.local-work/private/phase9/manual-ci-YYYYMMDD"
```

Script: [manual-jenkins-ci.py](../scripts/kubernetes/manual-jenkins-ci.py).

The helper records an exclusive request boundary **before** enabling the job or
sending the one build request. It never retries a build POST, even if the HTTP
response is ambiguous. Do not delete that boundary or choose a new directory to
circumvent it. Inspect queue/history first if a request or monitor is interrupted;
do not request another build without a new operator decision. A preparation-only
interruption may be retried against the same unchanged baseline. Preserve any
partial transferred bundle for diagnosis; preparation never overwrites it.

Use a persistent operator session for the monitor. Its `finally` block disables
the manual job and restores quiet mode after success, failure or a caught error.
A killed process or lost session may require an operator to restore that hold
through Jenkins; quiet mode alone does not abort a running build. The helper
fails if work is still queued/running or imported configuration/user hashes differ.
Authentication uses the current K3s administrator Secret and never prints it.

Archive actual JUnit/coverage and `migration-result.json`. Missing/deferred gates
are not PASS. No `gates.json` or publisher-eligible tarball is generated. Tests
use their existing disposable Docker database; do not mount or modify K3s
PostgreSQL data. Preserve the 90-minute pipeline timeout and current resources
for this first observation; report failures before changing bounds or retrying.

A zero helper exit means monitoring and hold verification completed; it does
not mean CI passed. Inspect `build-result.json` and the archived reports. The
[first attempt report](../docs/testreports/PHASE9_MANUAL_CI.md) records an aborted
network stall and a source-only reporting fix; do not delete its request guard
or rerun it to obtain a green result.

### Explicitly approved follow-up attempt

After reviewing a failed/stopped attempt and obtaining approval for one further
build, retain its entire evidence directory and pass it explicitly when preparing
a new directory. The helper requires the previous completed result, restored
hold, unchanged job/user state and sequential build history. It updates only the
held manual job definition and preserves all previous builds and request guards.

```bash
bash scripts/local-python.sh scripts/kubernetes/manual-jenkins-ci.py prepare \
  "$PWD/.local-work/private/phase9/manual-ci2-YYYYMMDD" \
  --previous "$PWD/.local-work/private/phase9/manual-ci-YYYYMMDD"
bash scripts/local-python.sh scripts/kubernetes/manual-jenkins-ci.py run \
  "$PWD/.local-work/private/phase9/manual-ci2-YYYYMMDD"
```

Script: [manual-jenkins-ci.py](../scripts/kubernetes/manual-jenkins-ci.py).

The 2026-10-22 correction sets `--mtu=1450` and
`--default-network-opt=bridge=com.docker.network.driver.mtu=1450` on the CI DinD
sidecar, matching the K3s pod interface. This covers the default build bridge and
new CI test networks. Roll out only `host-ci` while Jenkins is held; preserve the
bound work/cache PVCs. Verify MTU and bounded HTTPS downloads from both nested
network types before another application build. Do not relax network policies,
change application databases or enable publishing as part of this correction.
