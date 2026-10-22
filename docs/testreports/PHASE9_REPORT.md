# Phase 9 — Jenkins CI migration

Started: 2026-10-22. Status: **preparation in progress; no cutover or job activation**.
The operator authorized preparation after Phase 8 acceptance. The old Docker
controller, agents/publisher, build daemon, jobs, data and schedules remain intact.
The new K3s controller remains the isolated Phase 8 foundation.

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

The backup helper's fixture checks cover private file modes, no secret output,
explicit online inconsistency, missing-key rejection and suppressed tar errors.
These archive checks do not substitute for a real restore or CI acceptance.

## Remaining work and boundaries

No Phase 9 checkbox is complete yet: the inventory/preliminary preservation is
finished, but the first combined item also requires a consistent backup and
cutover preparation. Remaining work includes the reviewed cluster adaptations,
agent/daemon image availability and checks, consistent final backup, isolated
state restore, jobs/users/history validation, controlled CI and trusted publisher
activation, reviewed promotion/rollback and old-source retirement after acceptance.

The GitOps App access prerequisite is verified; promotion details remain pending.
A concrete
quiesce/stop window is needed for the final consistent backup/cutover; preparation
has not paused jobs or claimed permission for an unannounced outage.
No cluster resources, application checkout files, GitHub repository contents,
GHCR packages, credentials or live schedules were changed during this preparation.
No push or VM100/NAT cleanup was performed. Phase 9 remains open.
