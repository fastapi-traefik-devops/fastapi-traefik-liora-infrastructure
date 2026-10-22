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
| GitOps App / `gitops-app` | Infrastructure contents write; PR write for reviewed promotion | Not installed on infrastructure; PR write not granted |
| Trusted publisher / `ghcr-write` | Publish immutable GHCR images | Existing PoC identity preserved; fresh publish check pending |

> [!NOTE]
> HTTP 404 from the App installation endpoint means access was not
> verified; it does not prove the repository is absent. CI builds do
> not need infrastructure write or registry publishing credentials.

### If automated promotion PRs are chosen

- [ ] Arrange GitOps App access to the infrastructure repository with
      Pull requests: Read and write. Recheck the actual grants afterward.

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
