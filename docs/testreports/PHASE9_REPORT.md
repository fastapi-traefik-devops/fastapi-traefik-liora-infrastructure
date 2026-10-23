# Phase 9 — Jenkins CI migration

Latest execution: [authorized minimal live cycle](PHASE9_LIVE_CYCLE.md).
Application PR #62 passed its real required CI check and merged normally at
`38a7f2a`. The existing main/publisher jobs now use the reviewed repository split
and immutable helper bundle; no branch rule or App permission was changed.
Main #15 and trusted publisher #34 succeeded; Argo automatically deployed
`b8caf7e`. Manual STAGE verification passed with exact running digests and
strict-TLS UI/API smoke through the existing private edge route. Failed and
interrupted attempts are preserved. SCM polling then detected `3459d5a` and
main #16 / publisher #35 automatically deployed `59c3685`. The second manual
Argo/running-pair/HTTPS verification passed; only main polling remains active.

Started: 2026-10-22. Status: **Phase 9 in progress; minimal live STAGE cycle
and main-only polling verified; target acceptance work remains open**.
Earlier sections below describe their historical checkpoints; the linked live
report records current results. Current K3s admin, retained Jenkins state,
recovery inputs and PostgreSQL content remain protected.

Latest review: [publisher and promotion repository split](PHASE9_PUBLICATION_REVIEW.md).
The operator approved local implementation with automatic direct STAGE commits,
manual DEV/PROD and automatic STAGE acceptance as a mandatory PROD gate. This
supersedes earlier human approval for every GitOps PR. See the
[local implementation and activation gates](PHASE9_PUBLICATION_IMPLEMENTATION.md).
The latest priority narrows the initial path to existing CI → immutable
publication → direct STAGE update → Argo, with manual first-deployment checks.
Observer/receipts and expanded workflows are preserved for later. PROD is
explicitly blocked until automatic acceptance is implemented and live-verified.
The preserved optional observer remains outside the live initial path.
The main/publisher jobs and necessary egress are active for the verified minimal
cycle; automatic acceptance and PROD promotion remain blocked.

The separately authorized [Phase 10 fresh CNPG installation](PHASE10_REPORT.md)
supersedes database-data preservation for that database-only checkpoint. Phase 9
Jenkins work remains pending; database checks do not satisfy automatic STAGE
acceptance or authorize PROD image promotion. Jenkins login/history and private
recovery inputs remain protected throughout. Subsequent Jenkins checks must
use the current CNPG baseline, not require the retired `postgres-vol` PVCs.

## Next pending work

Follow the [ordered Phase 9 checklist](IMPLEMENTATION_PLAN.md#next-pending-work--execution-order):

1. Finish the startup quiet-mode guard cutover and verify controller restart.
2. Activate automatic STAGE observation and source/digest-bound receipts.
3. Extend the existing serialization lock through acceptance and verify stale/
   failed-acceptance/concurrent-update handling.
4. Complete manual DEV promotion with the existing pipelines/helpers.
5. Only after the automatic acceptance gate is live-verified, enable manual
   release-tag PROD promotion of the exact accepted pair without rebuilding.
6. Verify manual rollback before reviewing retirement of obsolete GitOps paths.

Main polling and trusted publication stay active; unrelated jobs, nightly
schedules and recurring indexing stay disabled. Scans/remediation remain
deferred. The checks above remain pending; no new execution is claimed here.

## Earlier CI-only checkpoint

[MTU correction and successful manual build #2](PHASE9_CI_RETRY.md).
The operator approved continuing after the [first aborted attempt](PHASE9_MANUAL_CI.md).
Default and new user-defined Docker bridges now use MTU 1450; bounded nested
HTTPS probes passed before activation. Build #2 at application `cb08cda` passed
all 13 functional gates and 96 tests, including both runtime-image health checks.
The formerly stalled Alpine step completed in 4.7 seconds. JSON/JUnit reporting
and cleanup passed; build #1 and all four of its archives are preserved.

At that earlier checkpoint all jobs were disabled, quiet mode restored, and
imported job/user hashes matched the baseline. The administrator and K3s
PostgreSQL data were unchanged; all five Argo CD applications were Synced/Healthy.
No security scan, publication, promotion, application deployment or Git push
occurred in that CI-only increment. Publishing and promotion across the
repository split remained open for the later review and execution described above.

## Confirmed decisions — 2026-10-22

The operator approved the existing privileged DinD approach for the initial K3s
migration, with a separate trusted publisher, bounded resources and a recreated
disposable build cache. Preserve required users, jobs, build records, retained
artifacts, credential IDs and encryption material **except legacy administrator
login data**: the current K3s admin account/password must remain authoritative.

Earlier checkpoint boundary (superseded for local source preparation by the
latest confirmed decisions linked above): migrate current settings and pipeline
sources without changing DEV/STAGE/PROD promotion behavior in that increment. Preserve originals and keep imported jobs
inactive pending operator review. The desired later target is main CI/publication
followed by a human-reviewed STAGE PR, and release-tag PROD promotion reusing
the STAGE-verified digest pair. These targets do not authorize running the
current publisher's legacy direct push or changing its source now. Gradual
activation remains the intended sequence after state verification.

The operator explicitly authorized immediately stopping the local kind cluster
and the full legacy Jenkins stack, while retaining everything for recovery.
This does not authorize container/volume deletion, VM100 retirement, Proxmox NAT
changes or stopping either remote K3s cluster.

## Authorized legacy shutdown and stopped-source backup

Executed the [standalone stop helper](../../scripts/kubernetes/stop-legacy-ci.py)
with `--stop-active`, matching the immediate-stop authorization. It privately
preserved all Jenkins bind inputs, including both agent connection secrets and
trusted publisher helpers, and full container inspection metadata. It entered
quiet mode and preserved queue details before canceling queued requests. At the
final stop boundary the queue was empty and 17 in-flight executor entries,
including Pipeline flyweight entries, remained. These are recorded privately;
**work was not fully drained and interrupted builds are not claimed successful**.

| Retained container | Stopped exit code |
| --- | --- |
| `host-jenkins` | 143 (SIGTERM) |
| `host-jenkins-agent` | 143 |
| `host-jenkins-publisher` | 143 |
| `host-jenkins-docker` | 0 |
| `fastapi-dev-control-plane` | 130 |

None was OOM-killed. No container or volume was deleted. The existing controller
image was used for a networkless, read-only volume-copy helper with all
capabilities dropped; its exited container is also retained. All local Docker
containers are now stopped, including the original kind node. The legacy
controller home and disposable cache remain in their original named volumes.

The completed private recovery directory is
`.local-work/private/phase9/stopped-20261022T101922Z/`: original stopped home,
all mounted Jenkins runtime inputs, original-path mappings, in-flight execution
metadata, pre/post-stop container records and a per-archive hash manifest.
Required configuration and encryption members were validated. The source copy
contains 30 job configurations, 139 build records and three user configurations;
the home archive is 375,082,528 bytes. All 14 archive hashes and private
directory/file modes were independently rechecked. The source copy is
**consistent=true, restore_tested=false**: this means a stopped-filesystem
snapshot, not that interrupted builds completed or that restore is proven.
The original legacy admin data remains in this recovery archive only; exclude
it from the migrated target while retaining the current K3s admin login.

Two stop-helper fixture tests passed: the immediate-stop path retains in-flight
metadata and stops only named containers without deletion, and forced controller
termination cannot produce a clean-backup manifest. The existing eight staging
and four online-backup tests also pass. No fixture secret appeared in output.

Both remote clusters were checked read-only after the legacy stop: all six
nodes Ready, K3s Jenkins available 1/1, all five Argo CD applications
Synced/Healthy. At that legacy-stop checkpoint the target foundation had not
yet been modified; the later state restore report supersedes that status.
Rollback still requires reconstructing missing original bind-source paths from
private archives before starting old containers; do not blindly restart them.
Source archives and partial/earlier preparation receipts have been retained.

## Verified source and runtime inventory

Application checkout is clean and read-only at
`b98a22e48527c256193ed65c10307eb574b27ab6`. Active JCasC, Job DSL, application
Jenkinsfile and trusted publication Jenkinsfile hashes match the reviewed source.
Deployment source history is already preserved under
`kubernetes/platform/upstream/infra/jenkins-host/`.

| Item | Observation |
| --- | --- |
| Docker components | `host-jenkins`, `host-jenkins-agent`, `host-jenkins-publisher`, `host-jenkins-docker` |
| Home | About 487MiB; named volume `host-jenkins-home` |
| Job configuration files | 30, including multibranch children, trusted publisher and smoke job |
| Build records | 120 |
| Local user directories | 3; preserve them and password hashes during final transfer |
| Executors | Controller 0; `host-ci` 1; `registry-publisher` 1; both agents online |
| Queue/executors at inventory | Empty queue and no active builds; not a freeze/consistency guarantee |
| Credential IDs/scopes | `github-ci-app` in `app-ci`; `ghcr-write` and `gitops-app` in `trusted` |
| CI workspace | About 59MiB |
| Publisher workspace | About 22MiB |
| DinD disk contents | About 9.6GiB; Docker reports ~5.75GB build cache |
| Local free disk before copy | About 6.4GiB; do not copy old build cache locally |

Container bind mounts still name the former repository path, including Secret
files. The active application checkout has no `.jenkins-host/` directory. Runtime
files remain available inside the running containers and were preserved directly.
Do not recreate/restart old containers from the missing old Compose paths.

Exact image IDs, mounts, plugin IDs, source hashes and private job metadata are
in ignored `.local-work/private/phase9/legacy-inventory.json`. They were gathered
through Docker/filesystem reads and authenticated read-only Jenkins APIs.
No credential values or raw XML were printed or committed.

## Online preservation copy — Not a consistent migration backup

Created `.local-work/private/phase9/online-20261022T073204Z/` containing:

- `home.tar.gz`: 374,673,141 bytes, including controller configuration, jobs,
  users and the original Jenkins encryption material.
- `runtime-inputs.tar.gz`: 25,307 bytes, including controller-mounted Secret
  inputs, JCasC, Job DSL and the active pipeline bind mounts.
- `manifest.json`: per-archive hashes, member counts and tar exit statuses.

Directory mode is 0700; archive/manifest files are 0600. Archive reading and
required recovery-member checks passed. This is a private, credential-bearing
online preservation copy: **consistent=false, restore_tested=false**. Jobs were
not paused and containers were not stopped. It does not satisfy the plan's final
consistent backup requirement and is not a restore test. Preserve it separately
in the operator's protected recovery storage; never add it to Git.

CI/publisher workspaces and disposable Docker cache are excluded. The reviewed
procedure calls for recreating cache on cluster storage and taking a final
consistent home/input snapshot after a drained, explicitly coordinated stop.

## GitHub App installation access

Read-only GET checks using in-memory App JWTs from the existing runtime keys found:

| Identity | Application repository | Infrastructure repository |
| --- | --- | --- |
| CI App | Contents read, PR read, statuses write verified | Installation access not verified (404); not needed for application builds |
| GitOps App | Contents write, PR write and metadata read verified | Contents write, PR write and metadata read verified |

Initial checks found missing infrastructure installation access and no PR write
grant. On 2026-10-22 the operator added both repository selections and granted
Contents/Pull requests write with Metadata read. A subsequent GET-only check
verified HTTP 200 and all expected permissions on both repositories. This closes
the installation permission gap. The CI App retains application-only access.
The exact GitHub setup/acceptance steps are in runbook 17 and linked from recovery
documentation. No keys were rotated or exposed, and no App settings, repository
contents, PRs or GitHub resources were changed by the checker. Actual future PR
creation/branch-protection behavior still needs controlled workflow verification.

The old trusted publisher still hardcodes the former monolithic repository and
direct STAGE pushes. It cannot be activated unchanged. Promotion remains under
discussion; the migration preserves existing behavior with necessary repository
adaptation and does not silently introduce a new mandatory promotion path.

## Prepared execution procedure

### Offline inactive-copy preparation

The standalone staging helper verified the online archive's manifest and wrote
`.local-work/private/phase9/staged-20261022T094005Z/` without extracting files or
contacting either controller. The original online backup remains unchanged.
The private directory is mode 0700; archive and manifest are mode 0600.

The copy retains all 30 job configurations, 120 build records and three user
configurations. A separate source/output hash comparison verified 6,067 unchanged
files byte-for-byte, including keys, credentials, users, history and artifacts.
All 29 executable jobs/multibranch projects are disabled, scan/timer
triggers removed and Pipeline resume disabled. The plain folder remains a
folder. Controller executors are zero; static agents, clouds, old startup hooks
and queued-work files are omitted only from the copy. A new quiet-mode startup
hook is included. The method signature was checked against the running 2.585
class API without executing any Groovy on the controller.

Fixture tests cover retained secret/history bytes and private output modes,
suppressed secret-bearing errors, missing keys, changed source hashes, unsafe
paths, unreviewed job types, links and duplicate normalized members. All eight
staging fixture tests and the existing four backup tests pass. Successful staging
is **not** a running restore test. The copy is explicitly marked
`consistent=false`, `restore_tested=false`, `ready_for_cutover=false`; final
consistent-backup support, target JCasC/user ownership and startup behavior still
need implementation/validation before cutover.

[Runbook 17](../../runbooks/17-migrate-jenkins-ci.md) records source/runtime mapping,
backup boundaries, App prerequisites, proposed agent/DinD/publisher placement and
resources, and the ordered consistent-backup/state-transfer/cutover/rollback
procedure. The proposed layout keeps the source labels and one-executor agents,
co-locates CI/DinD for shared nested-container work paths, and separates publishing.
Its PVCs/resources/network policy are proposals, not applied manifests.

Privileged DinD is an existing PoC requirement, not a new isolation guarantee.
Before activation, review that requirement, actual worker headroom and access
separation. Namespaces alone do not block publisher access to the build daemon.
A restored controller must start quiet, with jobs/triggers/agents disabled,
without executing imported Job DSL. Preserve old encryption keys with old
credentials and resolve existing users versus new foundation JCasC deliberately.

Standalone helpers:

- [Runtime inventory](../../scripts/kubernetes/inventory-legacy-jenkins.py).
- [Online preservation copy](../../scripts/kubernetes/backup-legacy-jenkins.py).
- [Read-only GitHub App access check](../../scripts/kubernetes/check-jenkins-github-access.py).
- [Offline inactive-copy preparation](../../scripts/kubernetes/stage-jenkins-home.py).
- [State transfer / verified-copy continuation](../../scripts/kubernetes/restore-jenkins-state.py).
- [Runtime acceptance without running jobs](../../scripts/kubernetes/verify-jenkins-migration.py).

The backup helper's fixture checks cover private file modes, no secret output,
explicit online inconsistency, missing-key rejection and suppressed tar errors.
These archive checks do not substitute for a real restore or CI acceptance.

## Remaining work and boundaries

### Operator Docker cleanup after the held restore

On 2026-10-22 the operator ran `docker system prune -a --volumes` on the local
execution host. Subsequent inspection found the stopped legacy containers and
local images removed, with the seven named Jenkins volumes still present.
All 14 stopped-source archive sizes and SHA-256 hashes match their private
manifest. The migrated controller is Ready, its two homes remain Bound, and all
six remote K3s nodes are Ready. Local cleanup did not modify those clusters.
Comparison with the preserved kind-container mount metadata also confirmed that
its anonymous data volume was removed. Jenkins archives do not back up that
kind cluster's state; do not claim the legacy kind cluster can resume in place.
The operator subsequently confirmed that its application environments contained
only default installation data: no application/database transfer from kind is
required. Keep the current K3s PostgreSQL content. This does not reduce the
separate Jenkins history/user/credential preservation requirement.

Legacy Docker rollback now needs container recreation from preserved private
metadata/source, restoration of missing bind inputs and available images.
It cannot rely on `docker start` or on the former local image tags. The exact
controller image was recovered from the complete audit export made before
cleanup. Agent/DinD registry tags were unavailable, so bounded rebuilds use the
unchanged preserved Dockerfiles and tool locks. These are new builds, not a
claim of byte-identical recovery: existing APK upgrade/install steps resolve
current packages. The later operator vulnerability deferral superseded the
blocking scan requirement for this increment; see the worker report.
Remaining operator data is preserved; no further pruning was performed.

Inventory, consistent source/foundation backups, concrete retained-home rollback
preparation, held state restore/acceptance and bounded worker deployment are
complete. Both image digests were published and the two original agent labels are
online, with publisher source hashes and Docker build/bind smoke verified.
The unchanged admin password passed API/browser again; jobs remain disabled and
no Jenkins job or application publish ran. Vulnerability remediation and further
image scans were explicitly deferred by the operator; failed findings were not
relabeled as passes. Remaining work includes pipeline/settings review,
controlled application CI and trusted publisher
activation, reviewed promotion/rollback and old-source retirement after acceptance.

The GitOps App access prerequisite is verified. The latest operator decisions
authorize the immediate legacy stop and define the desired later promotion
target, while deferring pipeline behavior changes to review. Target CI activation
remains unverified. Changes are confined to NONPROD Jenkins/controller and worker
resources, their private inputs and published infrastructure images. Application
files, application GHCR images, GitHub repository contents, current PostgreSQL
data and administrator credential values were not changed. No Git push,
source-data deletion by the migration helpers, VM100 retirement or NAT
cleanup was performed. Phase 9 remains open.
