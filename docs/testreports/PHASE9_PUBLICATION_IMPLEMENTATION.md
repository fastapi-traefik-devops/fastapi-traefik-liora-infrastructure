# Phase 9 — Local preparation of the initial STAGE cycle

Latest update: the operator authorized live activation. The
[live-attempt report](PHASE9_LIVE_CYCLE.md) records the application GH013 PR/check
blocker and unchanged execution hold. The local-only status below is the
historical preparation checkpoint, not the current authorization boundary.

Date: 2026-10-22. Status: **locally implemented/tested; live activation NOT approved
or performed; Phase 9 remains open**.

## Current priority and preserved target

The operator first approved automatic direct STAGE commits, replacing the earlier
human-review requirement for every GitOps PR. The subsequent priority is to get
the existing K3s CI/CD cycle working first, then finish the agreed architecture.

Initial cycle: application main → existing Jenkins CI → immutable publication →
direct STAGE pair update in infrastructure main → Argo deployment. Verify the
first deployment manually. DEV stays manual; PROD is explicitly blocked until
automatic STAGE acceptance is implemented AND live-verified. No manual check or
fixture receipt bypasses that block. Rollback remains manual.

Reuse the migrated controller/login/history, existing host-ci + DinD and separate
registry-publisher, 13 functional gates, runtime smoke tests and existing immutable
registry logic. No worker image rebuild, webhook service or new production data
migration is introduced. Security scans/remediation remain deferred.

## Local changes

Application source commits (all local, not pushed):

- `567694b`: opt-in tested-image export and explicit functional-only admission.
- `666aaf3`: separate source/infrastructure histories and preserved acceptance code.
- `3b37b50`: fuller prepared orchestration, retained in Git for the later increment.
- `d87b3c9599c5b79dfc6b6751739a110ecbb2ba96`: minimal initial Pipeline path,
  one main SCM poll, explicit PROD block and integrated fixture-cycle test.

The existing main Jenkinsfile uses the functional profile and exports the tested
runtime images. `candidate.json` binds source SHA, allowlisted Jenkins job/build,
13 successful gates, archive/report SHA256 and seven explicitly deferred steps;
`security_scanned:false`. The trusted publisher requires a completed SUCCESS
source run, independently checks revision/artifacts and explicitly selects
functional admission. Default scan-backed release admission is unchanged.
Build #2 has no candidate archives and cannot be relabeled as publishable.

The trusted initial publisher stops after immutable publication and the STAGE
update; it does not allocate an observer or require acceptance receipts. It
retains write-once SHA tags and checks remote digests against archive bytes.
The main job prepares one `pollSCM('H/2 * * * *')` trigger; no nightly cron,
webhook or recurring folder indexing is required. Imported PR/other jobs stay
held. The obsolete `ci/publish.sh` fails closed.

The shared writer checks ancestry/tags in application history and writes only
infrastructure overlays at `kubernetes/apps/liora/overlays/`. A Jenkins lock
serializes initial publication/promotion. Exact application main is rechecked
immediately before every STAGE push; any newer source supersedes the candidate,
even if its CI fails. Infrastructure non-fast-forward races retry from latest
main and preserve unrelated changes; permissions/rule failures do not retry.
Cross-repository head checking and pushing cannot be one atomic transaction.

Direct writes are limited to STAGE `kustomization.yaml`, `promotion.json` and
invalidation of an old `acceptance.json`. The initial path creates no acceptance
receipts. The future acceptance writer may write only that receipt. GitHub App
repository permissions do not enforce path restrictions; the pinned writer does.

Infrastructure helper/worker references are prepared at application `d87b3c9`.
The publisher bundle contains 27 files; the retained observer bundle contains
only `stage_acceptance.py`. Both are immutable and verified against Git objects.
The live publisher STILL mounts `jenkins-publisher-ci-b98a22e48527`; retain it
for rollback. No prepared bundle or manifest was applied.

`initial-cycle/` composes the existing agents with necessary controller DNS/public
HTTPS egress for GitHub/App tokens. It has NOT relaxed the live egress hold.
The separate zero-replica `acceptance/` overlay is excluded. It preserves read-only
STAGE/Argo RBAC and observer preparation for later; no new observer node, RBAC,
Pod or credential is needed to complete the initial cycle.

The manual CI helper supports default-false `prepare --export-images`, binding
that choice to the one-shot receipt. `run` cannot silently override it. No new
manual build was requested. Manifest validators use actual split paths, reject
placeholder/mixed-source pairs, and render all environments. A read-only PR
validation workflow is prepared for later and is not an initial-cycle dependency.

## Validation and limits

- **54 application tests passed**, including candidate/archive integrity,
  explicit deferrals, immutable publication, independent repository histories,
  exact-main rechecks, concurrent infrastructure preservation, transport-error
  redaction, the artifact-to-STAGE fixture cycle and the initial PROD block.
  Registry/HTTP behavior is mocked; Git writes go only to ephemeral local fixtures.
- **21 infrastructure tests passed**: pinned bundles/observer exclusion (7),
  one-shot manual helper/export receipt (7), permission-audit redaction (1),
  placeholder/mixed-pair validation (1), existing agent deployment helper (5).
- All three Pipeline definitions passed the existing Jenkins Declarative validator.
  Validation did not install them, run jobs or change users/configuration.
- All three application overlays passed immutable-image validation and strict
  kubeconform: **14 resources each**, no invalid/errors/skipped resources.
- Prepared initial overlay: **18 resources**, strict schema validation passed.
  Preserved observer overlay: **8 resources**, strict schema validation passed.
- Changed Python/shell syntax and read-only workflow permissions passed.
- The broader legacy `validate_phase1.py` completed its syntax/configuration
  checks but could not complete its final Docker Compose check: this management
  host has no Compose plugin. The unchanged legacy Docker stack was not started
  or modified. Jenkins worker images already contain their existing tooling.

Read-only K3s inspection confirmed the current STAGE imageID format is the
pullable manifest digest and Argo uses the expected infrastructure path/main.
This is compatibility evidence, not acceptance of a newly deployed candidate.
Neither the first live cycle nor deferred automatic acceptance has run.

## Permissions and activation blockers

The K3s credential audit verified GitOps App Contents/Pull requests write and
Metadata read grants on BOTH repositories. The CI App remains application-only
with Contents/PR read and status write. Keys remain in process memory; audit
output contains neither keys nor JWT/installation tokens. Its temporary
infrastructure inspection token was revoked (HTTP 204).

Authenticated rulesets and effective main rules were empty. Classic main
protection returned **403**, because this App lacks Administration read.
The repository owner subsequently inspected the infrastructure repository and
confirmed that it currently has no protected branch. Together with the empty
rulesets/effective main rules, this closes the inspection blocker: no App branch
exception or additional permission is currently needed for the initial STAGE
writer. The 403 remains historical API evidence, not a reason to request broader
App access. No actual push has been tested. No permission change, branch-rule
change, push or workaround was attempted.

Before a separately approved live checkpoint: recheck rules if changed, make the
reviewed source available, install the reviewed existing-job definitions/pins,
set the existing app-ci SCM to the application repository/main-only discovery,
verify scoped credentials and approve necessary controller GitHub egress.
Use a one-time index only if needed, keep recurring indexing off, and enable
only the selected main poll and trusted publisher. Do not replay imported DSL.
Then run/record one initial cycle and manually verify Argo, running pair and URL.

## Remaining target work and preservation

After that initial cycle, reuse the preserved observer/receipt helpers and
orchestration, extend the SAME publisher lock through observation, verify the
actual automated gate live, and only then review enabling manual PROD promotion.
Keep immutable digest reuse/no rebuild, release-tag checks and manual rollback.
Expanded DEV/PROD orchestration and PR workflow activation are later increments.
No duplicate pipeline or new migration is needed. See the explicit sequence in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and
[runbook 17](../../runbooks/17-migrate-jenkins-ci.md).

Final read-only Jenkins check: **29 disabled jobs, zero triggers, quiet mode,
zero controller executors/queued/running work, 141 build records, three persisted
users; current admin authentication succeeds**. Before/after validation/audit
checks preserved configuration and user hashes. No login/password change,
PostgreSQL write, recovery modification, image publication, deployment, live job
activation or GitHub push occurred.

Private sanitized receipts and rendered bundles are under
`.local-work/private/phase9/publication-local-20261022/`; credentials and operator
state remain ignored and outside Git.
