# Phase 09 — CI/CD ownership

Summary as of 2026-10-25. Environment: NONPROD CI, DEV, STAGE and PROD.

## Result

The target delivery path has recorded successful execution. Follow-up work
remains; the phase is not closed for every failure and recovery scenario.

| Capability | Recorded result |
| --- | --- |
| PR and nightly `full` gates | Passed; nightly main #24 did not publish. |
| Manual DEV | Passed through `dev-build` and trusted publication. |
| Automatic STAGE | Deployment and SHA/digest-bound acceptance passed. |
| Manual PROD | Reviewed releases `v1.0.0` and `v1.0.1` passed. |
| Rollback | Re-release to `v1.0.0` passed in about 8 minutes, without rebuild. |
| Observer bootstrap | Bundle/source equality and local installer tests passed. |

Source: [target-state execution report](history/target-state.md).
Earlier “PROD blocked”, scan-deferral and main-only scheduling statements
apply to their historical checkpoints. They do not describe this summary.

## Remaining work

- Implementation: database-aware application health and acceptance; automated bundle-pin PR preparation.
- Verification: held-controller restart/recovery, live failed-acceptance and concurrency scenarios, and unchanged re-release.
- Status check: application cleanup PR #78 merge is not established by the saved cleanup report.

The STAGE HTTP health response alone does not prove database connectivity.
See the [active plan](../../IMPLEMENTATION_PLAN.md#phase-9--move-promotion-and-ci-ownership).

## Records

| Checkpoint | Record |
| --- | --- |
| Migration inventory and preservation | [Original report](history/report.md) |
| Held state transfer | [Restore](history/state-restore.md) |
| Agent and DinD recovery | [Workers](history/workers.md) |
| CI proposal | [Pipeline review](history/pipeline-review.md) |
| Failed first CI attempt | [Manual CI](history/manual-ci.md) |
| MTU fix and successful second attempt | [CI retry](history/ci-retry.md) |
| Repository split proposal | [Publication review](history/publication-review.md) |
| Local preparation | [Publication implementation](history/publication-implementation.md) |
| Controlled and polled STAGE cycles | [Live cycle](history/live-cycle.md) |
| Accepted releases and rollback | [Target state](history/target-state.md) |
| Earlier plan, incident diagnostics and receipts | [Plan notes](history/plan-notes-2026-10-25.md) |

Operations: [CI/CD guide](../../../CI_CD.md) and
[Jenkins jobs](../../../../runbooks/27-configure-jenkins-jobs.md).
