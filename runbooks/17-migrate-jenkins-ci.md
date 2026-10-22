# Migrate the existing Jenkins CI to NONPROD K3s

**Where:** Original infrastructure checkout and read-only application source.

> [!IMPORTANT]
> **Status: Phase 9 preparation only.** No old jobs have been paused, no
> state has been restored, and no migrated agents, builds, or publishing
> have been activated. The operator authorized preparation after Phase 8.
> Promotion behavior and final cutover require the review below. Do not
> retire VM 100 or change NAT.

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
> This helper accepts the **online preservation** format only and always records
> `consistent=false`, `restore_tested=false`, `ready_for_cutover=false`. It does
> not implement the final consistent transfer or prove startup behavior. Do not
> restore this preview to the live controller. Target JCasC must also be reviewed:
> the Phase 8 foundation sets its own admin password, while the old JCasC imports
> active agents and Job DSL. Neither should be applied unchanged to migrated
> users/jobs. Plugin/image initialization hooks and all external bootstrap inputs
> also need review before an isolated startup test.

The hook follows Jenkins' [initialization hook mechanism](https://www.jenkins.io/doc/book/managing/groovy-hook-scripts/).
The four-argument quiet-mode method was checked against the running Jenkins 2.585
class API; no hook was executed on the running controller.

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

> [!IMPORTANT]
> **Review plan only.** The online helper does not implement the mutation
> steps below. Prepare standalone helpers and review their exact affected
> containers and PVCs before execution. These numbered items are not
> authorized cutover commands.

- [ ] Review the proposed sequence below, identify missing helpers and
      evidence, and record the affected containers/PVCs before seeking
      cutover approval.

### Proposed cutover sequence (not yet executable)

1. Back up the new foundation home as well as old controller inputs. Record both
   controller image/plugin hashes, job/build counts, users and credential scopes.
2. Agree a window; quiet old Jenkins, prevent new scan/timer work, and wait for
   every active CI/publisher executor and queue item to drain. Record their states.
   Do not interrupt an active publish or merely check a single idle sample.
3. Stop the old controller cleanly, preserving its container, named volume and
   runtime bind mounts. Take the final consistent home archive and matching
   encryption/secret inputs from the stopped state with a verified manifest.
   Do not restart it from a missing Compose source path.
4. Stop the new foundation controller before writing its PVC. Stage old state
   privately; preserve users, password hashes, master key, `hudson.util.Secret`,
   credentials, jobs/build records, fingerprints and required artifacts together.
5. Sanitize only the migration copy: no imported job DSL, no active agents,
   disable all jobs and scan/timer triggers, and enforce startup quiet mode before
   starting with the same plugin set. Preserve original configs in the backup.
   Old encrypted credentials require old encryption keys; do not combine them
   with a fresh controller key or copy only credentials XML. Existing users may
   supersede the foundation login; resolve JCasC user ownership deliberately.
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
      release behavior before enabling publisher promotion.
- [ ] Confirm the final tested image will be reused, not rebuilt at release.
- [ ] Record each later PR, package publish, deployment, and rollback
      check in the Phase 9 report when performed.

> [!NOTE]
> Trigger and promotion details remain under discussion. DEV → STAGE →
> PROD acceptance does not authorize forcing every release through DEV
> or changing the feature-branch/manual DEV model. Preparation has not
> performed a new PR, publish, deployment, or rollback test.
