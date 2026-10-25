# Historical phase planning and execution notes

Archived 2026-10-25 from the implementation plan. Earlier status and
authorizations describe their original checkpoint. Use the [phase summary](../REPORT.md).

## Phase 9 — Move promotion and CI ownership

Status: **in progress; automatic STAGE acceptance, restored gate profiles and manual DEV
deployment live since 2026-10-24; first PROD release `v1.0.0` and rollback drill done on
2026-10-25**. Target-state test report: [PHASE9_TARGET_STATE](target-state.md).
User guide and setup from zero: [CI/CD](../../../../CI_CD.md).
The current state and how it works are in [Current CI/CD state](#current-cicd-state--2026-10-25);
the text that follows it is the historical record of the migration.
Legacy Jenkins state is restored to a separate NONPROD home, preserving the
current K3s admin, users, history, credential scopes and encryption material.
Existing CI/DinD and trusted publisher agents are connected. After the MTU
correction, manual CI passed all 13 functional gates and 96 tests.

The reviewed minimal live cycle now works: controlled main #15 / publisher #34,
then SCM-polled main #16 / publisher #35. Both automatically updated
infrastructure STAGE and Argo deployed the exact image pair. Manual running
digest and strict HTTPS checks passed through the existing private edge route.
Only main SCM polling is active (`H/2 * * * *`); unrelated jobs, nightly schedules
and recurring folder indexing remain disabled. Automatic acceptance and expanded
manual promotion workflows remain open; PROD is explicitly blocked. See the
[live execution evidence](live-cycle.md), [worker acceptance](workers.md),
[Phase 9 report](report.md) and [runbook 17](../../../../../runbooks/17-install-operate-jenkins.md).

The [pipeline review](pipeline-review.md) is complete as a technical
inspection; the operator approved its CI-only proposal. It checked live disabled
jobs and the pinned source, and found application GitHub `main` four commits
ahead at `13aa29eb27abac01e9638cdf45f1414a4c3002a1`. No source, job, trigger or
controller policy was changed during that read-only review. Its earlier approved
checkpoint was one manual functional CI build without scans, publication,
promotion or deployment; later live authorization superseded that boundary.
The [first attempt](manual-ci.md) stopped at a nested-network stall.
The operator approved MTU alignment and one further attempt; [build #2](ci-retry.md)
passed all 13 functional gates and 96 tests, including both runtime-image smoke
checks. Native JSON/JUnit reporting, cleanup and hold restoration passed.
Publication/promotion and full/release attestation remain outside this checkpoint.

Operator cleanup update, 2026-10-22: `docker system prune -a --volumes`
removed the stopped local legacy containers and images. Seven named Jenkins
volumes and the private stopped-source archives remain; all 14 archive size/hash
checks passed after cleanup. Remote K3s homes and the retained-foundation rollback
are unaffected. Legacy Docker recovery requires container recreation and private
bind-input restoration, not restarting retained containers. Do not remove any
remaining source volumes or archives.
The legacy kind node's anonymous data volume was removed as well; its cluster
state is not part of the Jenkins backups or the K3s foundation rollback.
The operator confirmed that kind's demo/STAGE/PROD applications contained only
default installation data. No application/database transfer from kind is needed;
retain the current PostgreSQL content in K3s without replacement or reseeding.

Vulnerability deferral, 2026-10-22 (**superseded on 2026-10-24**: security gates run again on
pull requests, main and nightly; see the current state above): the operator explicitly accepted proceeding
with deployment for this educational setup and deferred remediation/further
vulnerability scanning. Preserve the failed DinD scan as a failed result and do
not run further image audits in this increment. This does not change the
selective job activation/PROD gate or current-admin preservation requirement.

Preserve the maximum working behavior from the application's Jenkins proof of
concept while adapting it to the nonprod K3s foundation and repository split.
GitOps App access and Contents/Pull requests write grants on both repositories
were verified on 2026-10-22 after the operator updated the installation.

### Current CI/CD state — 2026-10-25

Jenkins decisions are owned by Tatiana Zainullina (CI owner) since 2026-10-23. This section
supersedes the historical boundaries below where they differ: the vulnerability-scan deferral,
"no nightly schedule", "functional-only main candidate" and "PROD blocked" are no longer current.

#### What runs where

| Trigger | Jenkins job | Gate profile (`ci/phase1.py`) | Publishes | Target |
| --- | --- | --- | --- | --- |
| Pull request | `app-ci/PR-<n>` (multibranch, build started manually) | `full`: all 18 gates + `gitops` | no | — |
| Nightly, main | `app-ci/main`, `cron H 2 * * *` | `full`: all 18 gates + `gitops` | no | — |
| New commit on main | `app-ci/main`, `pollSCM H/2 * * * *` | `release`: config, secrets, dependency installs and audits, image builds, non-root smokes, Trivy, `attest` | yes | STAGE, automatic, with acceptance |
| Manual | `dev-build` (`BRANCH` parameter) | `dev` = `release` gates | yes | DEV, direct commit |
| Manual | `trusted/publish` with `ACTION=prod` | none: reuses the STAGE-accepted pair | no | PROD via reviewed infrastructure PR |

Both triggers of `app-ci/main` are declared in the application `Jenkinsfile`, so they live in Git
and replace triggers set in the job UI. Jenkins is private (Tailscale only), so GitHub cannot
send webhooks; main is polled and pull-request builds are started from the job page. Source
tests (lint, unit, integration, e2e) belong to the pull request; the `release` and `dev`
profiles re-verify what is actually deployed: secrets, dependency audits and the scanned images.

#### How a change reaches each environment

**STAGE (automatic).** `app-ci/main` runs `release`; `attest` writes `gates.json` with the SHA,
the passed gates and the SHA-256 of both scanned image archives. Main archives the tarballs and
`gates.json` and requests `trusted/publish` (`ACTION=stage`). The publisher runs on its own agent
with the only write credentials (`ghcr-write`, `gitops-app`) and executes helpers exclusively
from the pinned ConfigMap at `/opt/phase1-ci`, never from a build checkout. Under one Jenkins
lock (`liora-stage-promotion`) it:

1. verifies the source run is SUCCESS and its Git revision equals `gates.json`
   (`registry.py --mode release`); functional-only candidates are accepted solely from the
   manual `migration-ci` checkpoint;
2. skips the candidate if application main has moved on (`superseded`);
3. pushes `sha-<SHA>` images to GHCR (write-once: an existing tag with different bytes is refused);
4. updates `overlays/stage/kustomization.yaml` and `promotion.json`, removes the previous
   `acceptance.json`, validates all three overlays (`ci/validate.sh`) and commits directly to
   infrastructure main (`chore(gitops): update stage for <sha>`), rechecking main before push;
5. runs `ci/stage_acceptance.py` on the read-only `stage-observer` agent (namespace
   `jenkins-acceptance`, RBAC: get `app-stage` Application, get Deployments, list Pods): Argo
   Synced/Healthy at a revision containing the promotion, every Pod running exactly the published
   digests, and `https://stage.liora.aprt.info` serving the UI root and `health-check = true`
   (resolved to HAProxy `192.168.77.240` inside the Pod, see incidents);
6. commits the receipt as `overlays/stage/acceptance.json` (accepted or failed). A failed
   acceptance makes the publisher build red; nothing is rolled back automatically.

**DEV (manual, any branch).** Job `dev-build` (Pipeline script from SCM, branch `*/main`,
`Jenkinsfile.dev`, lightweight checkout on) fetches only `refs/heads/<BRANCH>`, runs the `dev`
profile on the real branch head and requests `trusted/publish` with `ACTION=dev`. The publisher
accepts `dev` only from `dev-build` and `stage` only from `app-ci/main`, publishes in release
mode and commits the two DEV overlay files directly to infrastructure main. DEV is never
superseded and has no acceptance. Deploying the SHA that DEV already runs is a no-op.

**PROD (manual release).** Implemented in application branch `ci/prod-promotion` (publisher
pin `ci/publisher-pin-9c2084c`), not yet merged. A release tags an accepted main SHA `vX.Y.Z` and
runs `trusted/publish` with `ACTION=prod`, `APP_SHA`, `RELEASE_TAG`. Nothing is built or
published: `promote.py` reads the `sha-<SHA>` digests from GHCR, requires the tag on that exact SHA
and an accepted STAGE receipt for exactly that pair in infrastructure history, and pushes the
review branch `promotion/prod/<tag>` (two PROD overlay files). Merging that PR deploys PROD
through its own Argo CD. Rollback re-releases an earlier tag; because its branch is already
merged, a fresh branch `promotion/prod/<tag>-redeploy-<infra sha>` is created; a release that
PROD already runs reports `unchanged`. Procedure: application `ci/RELEASE.md`.

**Validation of deployment manifests.** `ci/validate.sh` renders DEV, STAGE and PROD and runs
`validate_gitops.py` plus `kubeconform -strict`. Built-in kinds use the default schemas;
operator kinds use strict JSON schemas generated offline by `ci/crd_schema.py` from the
installed CRDs (`postgresql.cnpg.io/v1 Cluster`, `barmancloud.cnpg.io/v1 ObjectStore`,
`cert-manager.io/v1 Certificate`; identical in NONPROD and PROD). A kind without a schema fails
closed. The PR gate `gitops` validates a fresh clone of infrastructure main with the PR's
validator, so a new operator kind breaks an application PR instead of the STAGE promotion.
When operators are upgraded or new CRDs are added, regenerate the schemas with
`python3 ci/crd_schema.py <crd.json> <version>`.

#### Pinning the publisher helper bundle

Any change to the application `ci/` helpers takes effect only after the bundle is re-pinned:

1. In this repository set `SOURCE_COMMIT` in `scripts/kubernetes/prepare-jenkins-publisher-source.py`
   and the ConfigMap name in `kubernetes/platform/nonprod/jenkins/agents/workloads.yaml`
   (`jenkins-publisher-ci-<sha[:12]>`); merge through a PR.
2. On VM 200: `prepare-jenkins-publisher-source.py --output <new file>` (reads `ci/` from Git
   objects, verifies blob hashes, never overwrites) and compare `data_sha256`.
3. **First** `kubectl apply -f <bundle>` and confirm the ConfigMap exists, **then**
   `kubectl diff`/`apply -k kubernetes/platform/nonprod/jenkins/initial-cycle` (expected diff:
   only the bundle name) and `rollout status deploy/registry-publisher`.
4. If `Jenkinsfile.promote` changed: paste it into `trusted/publish` and approve it in
   In-process Script Approval.

Older ConfigMaps stay in the cluster for rollback. Live bundles on 2026-10-25:
`jenkins-publisher-ci-9c2084ceb24c`; the observer bundle `jenkins-acceptance-ci-8b584055a83c`
(own pin `OBSERVER_SOURCE_COMMIT`, installed with `deploy-jenkins-observer.py`, runbook 27 §3).

#### Evidence

| Application SHA | What | Infrastructure commits |
| --- | --- | --- |
| `62bf447` (PR #68) | first automatic STAGE cycle with acceptance | `5c0b7c2` promotion, `ecea2d2` accepted |
| `00862d5` (PR #69) | first `release` profile run, release-mode publication | `0155c04`, `fba9709` accepted |
| `f96cb41` (PR #70) | publisher with DEV support, STAGE unchanged | `e509095`, `54fd02a` accepted |
| `5243708` (PR #71) | `dev` = `release` gates | `9cbcfae`, `8f4d266` accepted |
| `cce22bf` (PR #73) | STAGE and first DEV deployment from Jenkins | `68c90bc`, `5d4a9fb` accepted; DEV `90ec738` |
| `cce22bf` | nightly `full`, `app-ci/main` #24, 2026-10-25 02:15, SUCCESS, no publication | — |
| `9bd6f60` (PR #58 head) | `dev-build`, DEV deployment | DEV `698889e` |
| `2a6e05a` (PR #58) | target-state STAGE cycle | `289f323`, `004b90e` accepted |
| `48b443f` (`v1.0.0`) | first PROD release | `e8c303f`, PR #15 `da4704a` |
| `2a6e05a` (`v1.0.1`) | second PROD release | `120abb7`, PR #16 `2026117` |
| `48b443f` (`v1.0.0`) | PROD rollback by re-release | `6e097f4`, PR #17 `a32e4db` |

Full-profile PR runs: PR #69 passed all 18 gates and `gitops` after the triage fixes below;
PR #58 passed again after pull requests returned to `full`. Details and timings:
[target-state test report](target-state.md).

#### Incidents and fixes, 2026-10-23 to 2026-10-25

| Problem | Cause | Fix |
| --- | --- | --- |
| Observer smoke could never pass | No hairpin NAT: `151.115.96.5` refuses connections from vnet77 | `hostAliases` to HAProxy `.240` and egress `.240:443` (infrastructure PR #3) |
| Observer Pod `RunContainerError` | Connection Secret mounted read-only at `/run/secrets` blocked the ServiceAccount token mount | Mount at `/run/agent-connection` (PR #4) |
| Observer node vanished after a controller restart | JCasC replaces the node list on start; the node was created in the UI | `stage-observer` declared in `agents/controller-config.yaml` (PR #6) |
| Publisher failed before the STAGE commit | `kubeconform -strict` had no schema for CNPG kinds, later for `Certificate` | Strict pinned CRD schemas, fail-closed (application PRs #67, #68) |
| First `full` run red | 13 CVEs in dev tools (filelock, virtualenv); 3 HIGH in nginx 1.30.5 | `uv.lock` upgrade; `nginx-unprivileged:1.30.6-alpine` (PR #69) |
| NONPROD OOM kills, nodes NotReady, Jenkins restart, STAGE DB Pending (2026-10-23/24) | Proxmox ballooning shrank K3s nodes to ~1.8–2.5 GiB | Fixed 8 GiB RAM per node (`4ce8dd5`); flaky e2e during the incident |
| First `dev-build` failed `secrets` | Checkout fetched all branches; gitleaks matched SHA-256 fields in an unmerged docs branch | Fetch only the selected branch (PR #73) |
| Publisher Pod stuck `ContainerCreating` | Deployment re-pinned before the new ConfigMap was applied | Order rule in the pinning procedure above |
| PR #75 unit gate failed | DB-dependent test placed in the unit test path | Moved to integration tests (PR #75) |

#### Temporary measures

- The restored startup quiet-mode hook (`init.groovy.d/00-migration-hold.groovy`) still holds
  the controller after every restart: cancel quiet mode after checking that only `app-ci/main`,
  `trusted/publish` and `dev-build` are enabled.
- Known acceptance gap: `/api/v1/utils/health-check/` returns `true` without a database, so
  STAGE acceptance does not prove database connectivity.

### Initial working cycle — completed checkpoint

**Minimal live cycle verified (2026-10-23).** The operator authorized reviewed
pushes, existing-job/helper installation, controller GitHub connectivity, one
controlled cycle, and main-only polling after manual STAGE verification.
Application PR #62 passed its real required Jenkins check (13 gates/96 tests)
and merged normally at `38a7f2aae320f3607b20ae1a5d14b8fa64768eca`. No branch
rule or App permission was changed. Infrastructure main remains unprotected
as confirmed by its owner. See the [live execution report](live-cycle.md).

- [x] Integrate reviewed application source through its required PR/check path.
      Preserve history and never execute the obsolete remote pipeline.
- [x] Install reviewed existing main/publisher definitions and immutable helper
      bundle `jenkins-publisher-ci-d87b3c9599c5`; enable only checkpoint jobs,
      controller GitHub egress and one-time related PR checks. Keep recurring
      folder indexing, nightly schedules and unrelated jobs disabled.
      Main #13 exposed broken imported Declarative bookkeeping; publisher #33
      exposed missing exact-script approval. Both were repaired under the hold,
      with failed/interrupted attempts retained. Controlled retry main #15 and
      publisher #34 succeeded; first STAGE manual verification
      passed at `b8caf7e`. The following SCM-polled cycle also passed at `59c3685`.

The initial K3s CI/CD cycle is complete. Continue toward the target below using
the same agents/DinD, 13 functional gates, tested-image export and trusted
immutable publisher. Preserve the implemented split-history writer, exact-main
rechecks, serial STAGE lock, file allowlist and concurrent-infrastructure retries.

The first approved live cycle is application main → existing main Jenkins CI →
immutable image publication → direct STAGE digest update in infrastructure main →
Argo automatic deployment. Verify that first deployment MANUALLY: Argo
Synced/Healthy, running pair and STAGE URL. Do not call that automated acceptance.

- [x] Under the received live authorization, adapt the existing app-ci main job and
      trusted publisher definitions/pins. Main uses one SCM poll every two minutes;
      keep recurring folder indexing/nightly schedules off. Filter discovery to
      main before any one-time index; keep all imported PR/other jobs disabled.
- [x] Verify GitHub App repository write grants and main protection. The App
      grants were verified by API; the repository owner confirmed that the
      infrastructure repository currently has no protected branch. Combined
      with empty rulesets/effective main rules, no branch exception is needed
      for the initial STAGE writer. The earlier API 403 is an inspection limit,
      now resolved by owner confirmation; no push was used as a test. Recheck
      if rules change. No permission or branch-rule changes are authorized.
- [x] Run the authorized first minimal live cycle and record manual STAGE
      verification tied to application SHA and both published/running digests.
      Main #15 / publisher #34 succeeded for `38a7f2a`; promotion `b8caf7e`
      became Argo Synced/Healthy. Both running digests match; UI/API HTTPS
      smoke passed through the existing private edge route with strict TLS.
      Current admin profile hashes and database pod/PVC identities are unchanged.
      This manual check is not automatic acceptance or a PROD gate.
- [x] Enable only main SCM polling (`H/2 * * * *`) after the verified cycle
      and demonstrate a meaningful new main commit reaches STAGE automatically.
      PR #63 passed its real check and merged normally at `3459d5a`. Native
      SCMTriggerCause requested main #16; publisher #35 committed `59c3685`.
      Argo Synced/Healthy, actual digest pair and HTTPS smoke passed again.
      All related PR jobs are disabled again; nightly schedules and recurring
      folder indexing remain disabled.

### Phase 9 work items — status

**2026-10-24 reconciliation:** automatic STAGE receipts and manual DEV are
present in live builds; treat items 2–4 below as completion/coverage review,
not instructions to build duplicate components. Reconcile the actual nightly/
indexing/PR-job settings with the approved policy. Preserve the current state
until that review is authorized; do not restore a historical main-only snapshot
as a side effect of documentation maintenance. See the
[current documentation review](../../../evidence/records/2026-10-24-operational-documentation-review.md#jenkins-documentation-boundary).

Status of the Phase 9 work items on 2026-10-25 (how each was done is described in the
current state above):

1. [ ] **Controller restart cutover.** Partly done: nodes are declared in JCasC and survive a
   restart (infrastructure PR #6). Open: the quiet-mode hook still requires a manual
   *Cancel Shutdown* after every restart.
2. [x] **Automatic STAGE acceptance.** Live since 2026-10-24 (application PR #65; infrastructure
   PRs #1, #3, #4, #6); five accepted cycles, see Evidence. The observer reaches STAGE through
   the private HAProxy route; fresh external reachability is not part of the check.
   Reproducible on a new controller: the observer bundle is pinned separately and generated
   byte-identical to the live one; `deploy-jenkins-observer.py` creates its connection Secret
   from the held controller (runbook 27 §3, [report](target-state.md#8-reproducible-observer-installation)).
3. [x] **Serialization through acceptance.** One `liora-stage-promotion` lock covers publication,
   the STAGE commit, observation and the receipt; superseded candidates are skipped and new
   promotions remove the previous receipt (fixture-tested). Open: a live failed-acceptance drill.
4. [x] **Manual DEV promotion.** Job `dev-build`, `ACTION=dev` (application PRs #70, #71, #73;
   infrastructure PR #10); first DEV deployment `90ec738` for `cce22bf`.
5. [x] **Manual PROD promotion — implemented.** `ACTION=prod` in `trusted/publish`, release by
   `vX.Y.Z` tag of an accepted SHA, review branch per release, rollback by re-release
   (application branch `ci/prod-promotion`, publisher pin `ci/publisher-pin-9c2084c`; 93 CI unit
   tests including release → release → rollback; rehearsal against copies of both repositories).
   **First live release** `v1.0.0` done on 2026-10-25: infrastructure PR #15, Argo PROD
   Synced/Healthy ~7 min after the merge, 2 + 2 Pods on the released digests, site and health
   check OK; `v1.0.1` followed (PR #16). See [target-state report](target-state.md).
6. [ ] **Rollback and obsolete paths.** Rollback by re-release is implemented and drilled live:
   `v1.0.1` → `v1.0.0` through `promotion/prod/v1.0.0-redeploy-2026117` (infrastructure PR #17),
   ~8 min to a working site, no rebuild. The obsolete application paths are reviewed
   ([cleanup report](../../../evidence/records/application-repository-cleanup.md)). Open: merge application PR #78; check
   the `unchanged` re-release live.
7. [x] **Return pull requests to `full`.** The temporary `pr` profile (2026-10-24/25) is removed;
   pull requests run all 18 gates again (application branch `ci/restore-full-pr-checks`).
8. [ ] **Acceptance database check** (close the health-check gap above).
9. [ ] **Automate bundle pinning** (a trusted job that prepares the pin PR after a merge).

The pinned bundle is re-pinned to a merge commit after each feature lands; content is identical,
only provenance changes. Branch-rule and GitHub App permission changes remain out of scope.

### Confirmed migration scope and activation boundary

- Keep the existing DinD approach with a privileged daemon alongside the CI
  agent; keep the trusted publisher separate. Measure resource/storage needs.
  Recreate the disposable Docker cache; preserve build history and artifacts.
- Preserve required Jenkins state, credential IDs and encryption keys, and other
  users, but **exclude the legacy `admin` login/account data**. Retain the current
  K3s administrator account and password; verify it after transfer.
- The original restore preserved Jenkins settings/pipeline sources. The current
  approved local adaptation changes only what the initial K3s STAGE cycle needs;
  retain originals and useful prepared target work. Only main and the reviewed
  trusted publisher are enabled; unrelated imported jobs stay disabled. Never
  execute the obsolete publisher unchanged.
- Confirmed current target (supersedes the earlier requirement for human review
  of every GitOps PR): successful CI of the resulting application `main` commit
  publishes immutable images, then automatically commits the exact digest pair
  directly to infrastructure `main`; Argo CD automatically deploys STAGE. There
  is no STAGE PR or human approval. DEV and PROD remain manual; PROD uses a
  release tag and the exact successfully STAGE-accepted pair without rebuilding.
- Serialize STAGE promotion and acceptance. Recheck application `main` immediately
  before each infrastructure push; skip superseded candidates, including when
  newer commits fail CI. Never fall back to an older candidate automatically.
  Preserve unrelated concurrent infrastructure changes through bounded retries.
- Automatically verify Argo CD Synced/Healthy, ready running frontend/backend
  digest pair and the STAGE HTTPS URL. Record evidence tied to application SHA,
  both digests and infrastructure/Argo revisions. Successful acceptance is a
  mandatory PROD gate. Rollback remains manual.
- The trusted direct writer may modify only STAGE `kustomization.yaml`,
  `promotion.json` and `acceptance.json`. Verify App permissions and applicable
  main-branch rule exceptions before activation; repository write permissions
  alone do not restrict paths. DEV/PROD use manual reviewed changes.
- The minimal live checkpoint is now explicitly authorized, including necessary
  reviewed pushes. Application integration and both controlled/polled STAGE
  cycles are complete; only the agreed main poll and trusted publisher are
  active. Do not change branch rules or App permissions.
- The operator authorized immediate stopping of the local legacy kind cluster
  and its Jenkins stack. Preserve containers, volumes, all recovery inputs and
  source; do not delete anything or change Proxmox NAT/VMs or remote K3s.
- Activate gradually after state verification: manual inert smoke, CI, then
  reviewed publication/promotion and finally polling/schedules. Preserving
  pipeline source does not authorize executing its old promotion behavior.

- [x] Inventory and privately back up the existing Jenkins home, jobs,
      plugin versions, build history/artifacts, encryption keys and required
      credential files before migration. Plan a consistent transfer/cutover
      without losing or duplicating active work. Keep source copies intact
      until the replacement is accepted. The operator's immediate-stop instruction
      superseded draining active work; interrupted executions were recorded and
      retained, not claimed successful. Both original homes remain intact and a
      concrete K3s foundation rollback object/procedure is prepared, not run-tested.
- [x] Restore required private state into a separate new controller home with
      compatible minimal JCasC and disabled execution. Preserve credential IDs/
      scopes, non-admin users, history/artifacts and original encryption keys;
      retain the current K3s admin login instead of importing the legacy admin.
      Verify the existing password in API/browser and check credential decryption.
      Keep all private state outside Git and diagnostics. Preserve original
      Job DSL/pipeline sources without executing them or redesigning promotion.
- [x] Review the preserved Job DSL/pipelines and settings with the operator
      before adapting old repository targets or enabling their behavior. Required
      initial CI-only runtime changes were approved there; the later local
      promotion adaptation is authorized by the current decisions above.
      Findings and the proposed minimal CI-only path are recorded in
      [the review](pipeline-review.md); operator agreement received.
- [x] After agreement, prepare the reviewed CI-only source/profile and manually
      trigger one build on `host-ci`, keeping every imported job and all polling,
      schedules, publication/promotion and legacy direct STAGE pushes disabled.
      Preserve existing admin login and K3s PostgreSQL content. Record exact source,
      functional test/build outcomes and deferred checks; restore the execution
      hold afterward. Leave release attestation unchanged in this CI-only increment.
      Attempt #1 is ABORTED after a nested-network stall; this checkbox records
      execution of the agreed single attempt, not passing full CI acceptance.
- [x] Review the [observed network stall and proposed MTU alignment](manual-ci.md)
      before changing CI worker settings or requesting another build. Verify
      nested HTTPS connectivity after any agreed change, review the source-only
      report fix, then explicitly authorize one new attempt with its own receipt.
      Preserve the first request guard/history and keep all publication held.
      Completed: both bridge MTUs are 1450, nested HTTPS probes passed, and
      [build #2](ci-retry.md) passed all functional gates and 96 tests.
      First-attempt history/archives and all imported job/user state are retained.
- [x] Move CI agents, isolated build daemon and separate registry publisher
      into the nonprod CI platform with bounded resources and fresh cache.
      Both preserved labels are online with one executor each; all new PVCs
      are Bound, helper source matches the reviewed commit and the Docker
      build/bind smoke passed. Current admin API/browser login and retained state
      passed again. Docker deployment details are adapted for K3s without giving
      application builds deployment credentials or using a host Docker socket.
      The operator accepted the existing privileged DinD requirement explicitly.
- [x] Review the retained publisher/promotion implementation for the repository
      split. [Findings and proposed changes](publication-review.md) identify
      required artifact evidence and separate Git histories. Its original STAGE PR
      proposal is superseded by the confirmed direct-commit policy above.
      That review held jobs/publication; the later authorized initial cycle is
      now active as recorded above.
- [x] Agree the explicit functional-artifact admission mode and proposed local
      implementation before editing pipelines. Operator approval includes exporting
      tested images with explicit deferred-scan evidence, adapting the trusted
      publisher, separating histories and updating pinned helpers/validators.
- [x] Implement and test locally with two independent fixture repositories and
      mocked remote APIs. Preserve read-only STAGE observation/evidence work for
      later; the initial publisher does not call it and PROD stays blocked.
      Verify App permissions/rules without changing them. See
      [implementation and activation boundary](publication-implementation.md).
- [x] Obtain explicit approval for the minimal live checkpoint, reviewed pushes,
      existing-job/helper setup and necessary GitHub connectivity. The owner
      authorized one controlled cycle followed by main-only polling and an
      automatic demonstration after manual STAGE verification. Application PR/check
      integration and the minimal live cycle are complete under that authorization.
- [x] After pipeline review, verify application build/publication credential
      separation, artifact provenance, SHA image tags and existing CI gates in
      controlled execution (main #15 / publisher #34). Image vulnerability handling
      follows the explicit educational-project deferral above; no further scans in this increment.
- [x] Keep build/test and image publication source in the application repository.
      Change promotion tooling to update infrastructure STAGE directly, with
      manual DEV/PROD review, rather than application `deploy/overlays/`.
- [x] Add local checks to render all overlays and reject placeholder/mixed-source
      images. PR-validation workflow is prepared for later; not an initial-cycle
      dependency.

Remaining live acceptance, manual promotion and rollback checks are tracked
in the ordered pending-work list above; none is implied complete by the
following initial-cutover result.

- [x] Activate main-only polling and trusted publication at the reviewed
      cutover. Main #16 / publisher #35 proved build/publish/STAGE deployment
      using only K3s workers, without VM 100 agents, bind mounts or Docker
      services. Private recovery copies remain retained. Nightly schedules and
      recurring folder indexing remain disabled; expanded workflows stay open.

**Pass:** working CI and the agreed automatic STAGE/manual DEV/PROD promotion
run from nonprod K3s, reuse the
proof of concept, preserve required state, and respect the two repository
boundaries. Report readiness for the operator's later VM 100/legacy NAT cleanup;
do not perform that cleanup as part of this implementation.
