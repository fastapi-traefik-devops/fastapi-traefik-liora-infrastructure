# Migrate the existing Jenkins CI to NONPROD K3s

Status: Phase 9 preparation only. No old jobs have been paused, no state has been
restored, and no migrated agents, builds or publishing have been activated.
The operator authorized preparation after Phase 8. Promotion behavior and final
cutover require the concrete review below. Do not retire VM100 or change NAT.

## 1. Inventory before mutation

Use the original infrastructure checkout and the read-only application source.
The preserved deployment source is `kubernetes/platform/upstream/infra/jenkins-host/`.
The application checkout still owns `Jenkinsfile`, `Jenkinsfile.promote` and `ci/`.

```bash
bash scripts/local-python.sh scripts/kubernetes/inventory-legacy-jenkins.py
```

[Standalone legacy inventory](../scripts/kubernetes/inventory-legacy-jenkins.py).
It writes private metadata under `.local-work/private/phase9/legacy-inventory.json`,
mode 0600. It reads job XML, controller configuration, credential IDs, mounts,
source hashes and authenticated queue/executor metadata without printing secret
values. It does not load jobs or call Jenkins mutation endpoints. A momentarily
empty queue is not evidence of a frozen/consistent Jenkins home.

The runtime bind mounts still refer to the former repository path. Do not restart
or recreate old Docker containers from that missing path. Read mounted runtime
inputs inside the running controller and preserve them before any cutover.
Compare their hashes with the retained source to identify intentional differences.
Keep old paths as provenance, not as dependencies of the replacement.

## 2. Preserve an online copy without claiming a cutover backup

```bash
bash scripts/local-python.sh scripts/kubernetes/backup-legacy-jenkins.py
```

[Standalone online preservation helper](../scripts/kubernetes/backup-legacy-jenkins.py).
It captures home and mounted runtime/secret inputs to timestamped mode-0700
subdirectories, with mode-0600 archives and a SHA-256 manifest. It validates
required controller configuration and encryption inputs. Nothing is restored,
paused or stopped. Tar exit 1 may indicate online changes; the manifest retains
its status. A hard tar failure or missing key fails without dumping diagnostics.

The output is private plaintext credential-bearing operator data. Protect it
like the existing recovery kit, and preserve it independently of the checkout
before cleaning `.local-work/`. Do not paste archive contents into reports or Git.
The helper labels every copy `consistent: false` and `restore_tested: false`.
It does not copy CI/publisher workspaces or the Docker build cache. Do not use it
as evidence that the final transfer can safely be performed while jobs run.

## 3. Verify GitHub App installation scope (read-only)

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

The operator must grant the existing GitOps App access to the infrastructure
repository and Pull requests: Read and write if automated PR creation is chosen.
Recheck actual grants afterward. HTTP 404 from the App installation endpoint
means installation access was not verified, not that the repository is absent.
CI builds do not need infrastructure write or registry publishing credentials.

## 4. Prepare cluster adaptation before running agents

Preserve the working names/labels `host-ci` and `registry-publisher`, one executor
each, controller zero executors. Keep the existing agent and DinD image/tool
locks; do not upgrade dependencies as a side effect of migration. Publish pinned
agent/daemon images only when the active manifests and image audit are ready.
Trusted pipeline/helper source must come from a reviewed pinned revision, never
from an untrusted build checkout or a mutable host bind mount.

Proposed placement, pending implementation review:

| Component | Placement | Request / limit | Storage / access |
| --- | --- | --- | --- |
| Controller | Existing `jenkins` namespace | Existing 100m/512Mi; 1 CPU/768Mi | Existing 5Gi home; assess actual expanded state size before transfer |
| CI agent | `jenkins-ci`, one Pod with DinD | Proposed 100m/192Mi; 500m/384Mi | Shared agent work volume; agent connection Secret only |
| DinD | Sidecar in CI Pod | Proposed 250m/1Gi; 1500m/2560Mi | Proposed 20Gi local-path cache and 5Gi shared work; private generated TLS client/server volumes |
| Publisher | `jenkins-publisher`, separate Pod | Proposed 100m/256Mi; 500m/512Mi | Proposed 5Gi work; no build-daemon certificates or Docker socket |

These are proposed PVCs/budgets, not created resources. Check node allocatable
requests and existing workloads before applying. The source explicitly requires
privileged DinD; this provides no kernel isolation from its worker VM. Review
that existing privilege requirement before enabling it in K3s, keep service-account
tokens and host Docker socket absent, and preserve logical build/publication
separation. A same-Pod agent/DinD layout keeps the work path identical inside
containers launched by nested Docker. Native sidecar timing/storage permissions
must be verified rather than assumed. The publisher must not reach the build
TLS endpoint; namespaces alone do not supply network isolation. Prepare a precise
policy for these CI Pods before activation, without changing unrelated services.

Recreate the disposable build cache. The old DinD data is about 9.6GiB on disk;
the execution host has only about 6.4GiB free before this preservation copy.
Do not copy/rebuild every layer locally or delete old cache automatically.

## 5. Review the final consistent backup and cutover procedure

The online helper does not implement these mutation steps. Prepare standalone
helpers and review their exact affected containers/PVCs before execution:

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

Rollback before target publication: stop new agents/controller, preserve target
state, and resume the original stopped controller using its retained container
and unchanged home/inputs. Rollback after publication needs review of completed
registry/repository side effects; restarting old polling is not an automatic undo.
No rollback procedure may discard build history or restore mismatched keys.

## 6. Resolve promotion before activation

The old publisher automatically writes STAGE to the former repository's main
branch. Do not run it unchanged. Preserve the verified-artifact and trusted
publisher boundary, but adapt the target to this infrastructure repository.
Trigger/promotion details remain under discussion. The generic plan's DEV →
STAGE → PROD acceptance sequence is not approval to force every release through
DEV or change the existing feature-branch/manual DEV model.

Agree branch triggers, digest selection/reuse, PR review and PROD release behavior
before activating publisher promotion. The final tested image must not be rebuilt
at release. No new GitHub PR, package publish, deployment or rollback test was
performed during preparation. Record each later action in the Phase 9 report.
