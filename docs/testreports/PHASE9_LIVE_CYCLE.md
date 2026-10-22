# Phase 9 — Authorized live cycle: application integration blocked

Latest continuation: the owner pushed `migration/phase9-k3s-bootstrap` and
opened application [PR #62](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/pull/62)
at `827b9be`. The existing required CI App identity matches `5369826`.
The current bootstrap check is `app-ci/PR-62 #2`, running the existing functional
profile on host-ci without export/publication. Main and trusted publisher remain
disabled; all unrelated imported jobs remain disabled. This continuation is
covered by the existing live authorization; branch rules/permissions are unchanged.

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
Results of the PR, main/publisher and polling cycles are pending.

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
