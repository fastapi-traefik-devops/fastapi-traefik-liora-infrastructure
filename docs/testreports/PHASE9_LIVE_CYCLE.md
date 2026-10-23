# Phase 9 — Minimal live CI/CD cycle verified

Final checkpoint, 2026-10-23: **controlled and SCM-polled cycles verified**.
Main #15 / publisher #34 deployed `b8caf7e`; main #16 / publisher #35
automatically deployed `59c3685` for application `3459d5a`. Main-only polling
is active. Argo Synced/Healthy, ready running digests and strict HTTPS smoke
passed. Verification was manual, through the existing private HAProxy route;
automatic acceptance is deferred and PROD remains blocked. Historical attempts
and their original outcomes follow below.

Latest continuation: the owner pushed `migration/phase9-k3s-bootstrap` and
opened application [PR #62](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/pull/62)
at `827b9be`. The existing required CI App identity matches `5369826`.
Bootstrap check `app-ci/PR-62 #2` ran the existing functional
profile on host-ci without export/publication and succeeded. Main and trusted
publisher were then installed for the controlled cycle; all unrelated imported
jobs remain disabled. See the dated retry section below for current progress.
This continuation is covered by the existing live authorization; branch rules/permissions are unchanged.

The one-time discovery changed the existing app-ci source to the application
repository with `main PR-62` filtering and orphan pruning disabled to preserve
history. The CI worker was temporarily held offline during discovery. Its
automatic PR #1 allocation was canceled and recorded ABORTED before functional
gates; the execution hold was restored before requesting controlled PR #2.
No imported build was deleted. The existing 12 main/30 publisher historical
builds were marked keep-forever to prevent the configured retention policy
pruning them during activation.

Controller DNS/public HTTPS connectivity and the reviewed immutable publisher
bundle `jenkins-publisher-ci-d87b3c9599c5` are installed. The publisher definition
was validated and installed disabled with explicit ACTION/SOURCE_JOB/CI_BUILD
parameters. No observer resources were activated; PROD remains blocked.
PR #62 check #2 passed all 13 functional gates and 96 tests; GitHub received
`continuous-integration/jenkins/pr-merge=success` from the expected CI App. The
normal merge produced `38a7f2aae320f3607b20ae1a5d14b8fa64768eca`; local application
main was fast-forwarded without rewriting history.

Controlled main #13 failed before agent allocation in
`DeclarativeJobPropertyTrackerAction.getTriggers`: the restored job-level
bookkeeping had a null trigger set. The execution hold was restored immediately;
no functional gate or publication ran. Private pre-repair configs and console/
native JSON remain preserved. The same corruption was confirmed on the publisher.
The repair removed only broken job-level bookkeeping on those two held jobs;
Jenkins recreates it from the reviewed definition. Original build records and
credentials remain intact. The offline staging helper now drops that obsolete
bookkeeping instead of deleting a nested field and leaving an invalid action;
12 staging regression tests and the live-client credential test passed.
Controlled retry main #14 ran against `38a7f2a`; publisher #33 failed before
script execution as detailed below. Polling remains off.

The meaningful follow-up is documentation commit `ce4b8fa` in
[PR #63](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/pull/63),
clarifying manual archive export versus normal publication. It must pass the
existing required check before normal merge. One-time indexing now uses the
standard suppress-index/event-build branch property so discovery cannot request
extra main builds; main SCM polling remains a separate, initially disabled
trigger. No recurring indexing or webhook was added. Main/publisher and polling
cycle results are still pending.

Historical first-attempt status: **blocked before Jenkins activation**. The operator explicitly authorized
reviewed GitHub pushes, existing-job/helper installation, necessary controller
GitHub connectivity, one controlled STAGE cycle and then main-only SCM polling.
No new authorization is needed for those actions once the integration blocker is
resolved. Branch rules/App permissions must not be changed or bypassed.

## Preflight and outgoing source

Read the implementation plan, Phase 9 reports and both clean repositories.
Fetched both remote main branches and reviewed outgoing commit subjects/bodies
and aggregate diffs. Reused the prepared existing-agent/publisher implementation;
observer/automatic acceptance remain deferred and PROD explicitly blocked.

The existing Jenkins folder still points to the legacy application repository.
All 29 jobs were disabled, triggers zero, controller quiet, queue/running zero,
with both existing agents online. Next existing build numbers were main #13 and
publisher #33; neither was requested.

Found one required sequencing fix: a Declarative `pollSCM` would activate at the
beginning of the first controlled run. Application commit `827b9be` removes that
trigger declaration and documents installing the existing main job's poll only
after manual first-cycle acceptance. The revised Jenkinsfile passed the existing
Jenkins Declarative validator without installation. Previous functional tests
and prepared publisher/helpers remain unchanged.

## Confirmed blocker and actual pushes

The application `git push origin main` was rejected with **GH013**:

- Changes must be made through a pull request.
- Required status check `continuous-integration/jenkins/pr-merge` is expected.

This concerns the APPLICATION repository. The owner's confirmation that
INFRASTRUCTURE has no protected branch remains valid. No branch rule or App
permission was modified, no bypass attempted, and no required status fabricated.
The application commits must be integrated through a PR satisfying the required
check/review rules before the existing main CI can fetch them. That integration
is unresolved; do not activate an obsolete remote Jenkinsfile as a workaround.

The shell command continued after the application rejection and successfully
pushed the already reviewed infrastructure commits `f39f741..864f280`. This did
not meet the intended application-first order. Those infrastructure changes
contain prepared source, documentation and optional manifests; no active app
manifest or live resource was changed. There was no force-push/history rewrite.
The execution stopped here, before job, helper, connectivity or polling changes.
Application remote main remains `13aa29eb27abac01e9638cdf45f1414a4c3002a1`;
application local main includes the preserved prepared commits and `827b9be`.

## Preserved execution boundary

Post-rejection verification compared the complete Jenkins snapshot against the
preflight baseline: **identical**, including job configuration/user hashes,
29 disabled jobs, zero triggers, quiet mode and zero queued/running work.
No state mutation was needed to restore the hold because activation never began.
The current admin authentication still succeeds; retained history, credentials,
recovery inputs and K3s PostgreSQL data were not modified.

No CI or publisher build ran. No image publication, STAGE promotion commit,
new Argo deployment or STAGE acceptance is claimed. Polling remains disabled.
Observer manifests/receipts remain outside the initial path; PROD stays blocked.
No scans/remediation were performed. Application rollback was not required.

Private baseline/held-state receipts and encrypted Jenkins configuration backups
are preserved in `.local-work/private/phase9/live-cycle-20261022/`. A not-executed
live-operation helper draft is retained there as preparation, outside tracked
source and outside the activation path.

## Resume sequence

1. Resolve application PR/required-check integration through the existing rules;
   do not change/bypass permissions or activate unrelated imported jobs.
2. Recheck both repository tips and publish any remaining reviewed infrastructure
   updates normally. If the application integration changes the source tip,
   reconcile the reviewed helper pin before installation.
3. Continue the already authorized existing-job/SCM/helper/connectivity setup,
   controlled CI → immutable publication → direct infrastructure STAGE update.
4. Manually record successful CI/publisher IDs, application SHA, digest pair,
   promotion commit, Argo Synced/Healthy, running pair and URL smoke.
5. Only then enable the main job's approximately two-minute SCM poll and prove
   a meaningful new main commit reaches STAGE automatically. Keep every other
   imported job, nightly schedule and recurring indexing disabled.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). This is a blocker report,
not another readiness approval requirement or a completed live checkpoint.

## Publisher approval correction and controlled retry (2026-10-23)

Main #14 passed all functional gates and exported images, but publisher #33
failed before Pipeline execution: the installed unsandboxed trusted definition
required Jenkins script approval. No registry or GitOps write occurred. The hold
was restored and the exact reviewed definition was approved by its SHA-256
`babb16963e2f30df72b54546484206cfa34e5f820860b20d8e3c862913817f98`;
no other script or signature was approved. The live helper and runbook now make
this prerequisite explicit.

Quiet mode paused interrupted finalization. With every job/trigger disabled and
the queue empty, canceling quiet mode allowed it to settle: main #14 and PR #63
#1 finalized ABORTED. Their records/artifacts are retained, without relabeling
their results. Main #15 is the controlled retry against `38a7f2a`; it must finish
SUCCESS before trusted publisher #34 may use its artifacts. Polling stays off.

## Controlled CI and publication results

- Application main: `38a7f2aae320f3607b20ae1a5d14b8fa64768eca`.
- Existing `app-ci/main #15`: completed SUCCESS, 13 functional gates,
  native JUnit 96 passed / 0 failed / 0 skipped; duration 1,588,191 ms.
- Separate `trusted/publish #34`: completed SUCCESS, duration 329,533 ms.
  Candidate source/build/hash checks passed before registry credentials were
  bound; both immutable registry artifacts were verified.
- Direct infrastructure STAGE commit:
  `b8caf7e2ee1d4ded226b6bce61fa1d76c59cb3bf`, changing only STAGE
  `kustomization.yaml` and `promotion.json`. Local infrastructure fast-forwarded
  normally while retaining the uncommitted documentation edits.

| Image | Published digest |
| --- | --- |
| Backend | `sha256:cc32c4e72a58a5b1b579e1909d9c31c455ebee3cba0a431bd957ecf51e9c2d0c` |
| Frontend | `sha256:87acf879741853a6e3d43c766ad0d93d488adf12b4e89891b9295739d6f6b0b5` |

Both use immutable tags `sha-38a7f2aae320f3607b20ae1a5d14b8fa64768eca`.
Manual verification completed at 2026-10-23 05:46 UTC:

- Argo automatically reconciled to `b8caf7e`: Synced/Healthy, operation Succeeded.
  No manual refresh/sync was requested. The existing prestart hook succeeded.
- Backend `backend-988c5d898-twsr6` and frontend `frontend-546bb6c455-c8lnd`
  are Ready and their actual `imageID` digests exactly match the table above.
- `https://stage.liora.aprt.info/` returned HTTP 200 with the application root;
  `/api/v1/utils/health-check/` returned HTTP 200 and JSON `true`. Strict TLS
  verification passed. These checks used Phase 7's existing resolver override
  to private HAProxy `192.168.77.240`, preserving Host/SNI/certificate checks.
  Public-origin TCP from this management host is refused; fresh external public
  reachability is not claimed and DNS/NAT were not changed.
- Current persisted user hashes match baseline. DEV/STAGE/PROD database pod UIDs,
  PVC UIDs and bound volume names are unchanged. No SQL/data migration or reseed
  was performed by the operator; normal application prestart ran during sync.
- Main #15/publisher #34 are kept forever alongside failed/interrupted attempts
  and imported history. Private evidence is under
  `.local-work/private/phase9/live-cycle-20261022/first-stage/`.

This is operator-invoked manual verification, not automatic acceptance:
`automatic_acceptance=false`, `prod_gate_satisfied=false`. No acceptance receipt
was committed. Observer resources remain inactive and PROD remains blocked.
Polling remains disabled until the related PR check completes and the worker
settles; PR #63 must pass its required check before normal merge for the later
polling demonstration.

## Main-only polling activation and automatic demonstration

After the verified first deployment, application PR #63 passed the real existing
required check (`app-ci/PR-63 #2`, all 13 functional gates and 96 tests). Its
job was disabled again and retained. Discovery now includes only `main`, with
orphan pruning disabled and index/event-triggered builds suppressed. Recurring
folder indexing and nightly schedules remain off.

The sole main trigger is `hudson.triggers.SCMTrigger`, `H/2 * * * *`. The normal
PR merge then produced `3459d5a4f1d39473fd845674dfc7f591bee81059`; the change
clarifies `ci/README.md`, with no pipeline or application behavior changes.
Local application main fast-forwarded normally. Polling automatically requested
`app-ci/main #16`; its native cause is exactly
`hudson.triggers.SCMTrigger$SCMTriggerCause` and checkout matches that full merge
SHA. No manual main-build request, webhook setup, branch-rule change or fabricated
status was used. Main #16 completed SUCCESS in 1,536,106 ms, with all 13
functional gates and native JUnit 96 passed / 0 failed / 0 skipped. Separate
publisher #35 completed SUCCESS in 273,304 ms and directly committed
`59c36854e8c2533c450821b718d39bb3f8f4946e`.

The second promotion changed only STAGE `kustomization.yaml` and `promotion.json`.
The intervening infrastructure documentation/helper commits remain ancestors
and were preserved. This documentation-only application change produced the
same image bytes/digests listed above; new immutable tags are
`sha-3459d5a4f1d39473fd845674dfc7f591bee81059`. Both the candidate and running
pod specifications identify that exact new main SHA. No images were rebuilt
for PROD and no PROD action ran.

Manual verification at 2026-10-23 07:29 UTC found:

- Argo Synced/Healthy at `59c3685`, operation Succeeded. Deployment followed the
  direct Git commit automatically; no manual sync or refresh was requested.
- Ready backend `backend-7b57c5d7f8-z7t8g` and frontend
  `frontend-6c67f8cbf5-7k2kb` use the new SHA-tagged references. Their actual
  `imageID` digests exactly match publisher #35's verified pair.
- UI and API health URLs again returned HTTP 200 with expected bodies and
  valid TLS through private HAProxy `192.168.77.240`. The same external-
  reachability limitation described above applies; no new public-origin
  reachability claim is made.
- Final current user hashes, all original 12 main / 30 publisher build IDs
  (keep-forever), unrelated job states/build counts, database pod/PVC UIDs and
  volume bindings match the baseline. Successful and failed checkpoint records
  are retained. Queue/running counts are zero, controller executors are zero.
- Exactly main and trusted publisher are enabled; every other job is disabled.
  Main retains its sole `H/2 * * * *` SCM trigger after the second run, publisher
  has none, and recurring folder indexing/nightly schedules remain disabled.

Private receipts are under
`.local-work/private/phase9/live-cycle-20261022/automatic-stage/`, with native
source-cause, test, preservation and original console evidence alongside it.
No credentials, private keys, recovery inputs or generated evidence were added
to Git. Both repositories were integrated by normal pushes/merges and
fast-forwards; no force-push, rebase or history rewrite was used.

## Validation and remaining boundary

- Registry/promotion fixtures: 27 tests passed, including stale main (even a
  failed/unbuilt newer commit), immediate pre-push recheck, concurrent unrelated
  infrastructure updates, immutable-tag protection and blocked PROD.
- Live-control client: 3 tests passed, including credential-output protection
  and rejection of Jenkins HTTP-200 assertion failures. Read-only live success
  and failure probes confirmed that completion detection; no job state changed.
- All three overlays rendered and passed semantic/schema validation: 14 valid
  resources each, no invalid/error/skipped resources.
- No additional vulnerability scan/remediation, operator SQL/data restore,
  database reseed, credential rotation, observer installation or branch/App
  permission change was performed.

The initial working-cycle checkpoint is complete. Phase 9's remaining target
work is the preserved separate observer/automatic acceptance gate and expanded
manual DEV/PROD workflows. PROD stays explicitly blocked until that automatic
gate is implemented and verified; these manual receipts do not qualify it.
Rollback remains manual and was not exercised by this checkpoint.

The migration startup quiet-mode hook is still retained. After a controller
restart, inspect the approved job/trigger states before deliberately canceling
quiet mode. Adapting that guard and verifying restart behavior is recorded as
a follow-up; automatic continuation across controller restart is not claimed.
No controller restart or unrelated infrastructure change was needed here.
