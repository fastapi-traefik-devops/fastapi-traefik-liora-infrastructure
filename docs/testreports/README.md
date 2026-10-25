# Implementation reports and history

Use [operator procedures](../../runbooks/README.md) for current actions and
[architecture](../ARCHITECTURE.md) for the desired system. Reports retain
point-in-time results; later decisions and reports supersede earlier status.

## Current planning and capability status

- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Operational documentation review and recovery capability register](OPERATIONAL_DOCUMENTATION_REVIEW_2026-10-24.md)
- [Architecture decisions](ARCHITECTURE_DECISIONS_2026-10-24.md)

## Delivery, databases and recovery

- [24 October disaster recovery test report](DISASTER_RECOVERY_TEST_REPORT.md) and [evidence package](disaster-recovery-test/README.md)
- [Phase 9 Jenkins migration](PHASE9_REPORT.md), [live cycle](PHASE9_LIVE_CYCLE.md), [state restoration](PHASE9_STATE_RESTORE.md), [workers](PHASE9_WORKERS.md), [target state and first PROD release](PHASE9_TARGET_STATE.md)
- [Phase 10 fresh CNPG installation](PHASE10_REPORT.md)
- [Phase 10.2 R2 physical backup/WAL and isolated PITR](PHASE10_2_REPORT.md)
- [Live PostgreSQL and etcd recovery procedures](RECOVERY_RUNBOOKS_2026-10-25.md)
- [Native etcd snapshot backups to R2](ETCD_R2_BACKUPS_2026-10-25.md)
- [Phase 11 certificates and refinement](PHASE11_REPORT.md)
- [Backup incident and retained-cycle recovery](BACKUP_INCIDENT_2026-10-24.md)
- [Backup alert review](BACKUP_ALERTING_REVIEW_2026-10-24.md), [alerting correction](ALERTING_OPTIMIZATION_2026-10-24.md), [storage/replication alerting](STORAGE_REPLICATION_ALERTS_2026-10-24.md)
- [Slack notification deployment](SLACK_ALERTING_DEPLOYMENT_2026-10-23.md)

## Earlier infrastructure phases

[Phase 0](PHASE0_BASELINE.md) · [Phase 1](PHASE1_REPORT.md) ·
[Phase 2](PHASE2_REPORT.md) · [Phase 3](PHASE3_REPORT.md) ·
[Phase 4](PHASE4_REPORT.md) · [Phase 5](PHASE5_REPORT.md) ·
[Phase 6](PHASE6_REPORT.md) · [Phase 7](PHASE7_REPORT.md) ·
[Phase 8](PHASE8_REPORT.md).

Historical command snapshots and their originating runbooks are indexed in the
[documentation review](OPERATIONAL_DOCUMENTATION_REVIEW_2026-10-24.md#historical-procedure-preservation).
They preserve one-time migration instructions and evidence; they are not steps
required for a fresh deployment or disaster recovery.

## Historical design and operator workspace

- [Cilium alternative discussion](NETWORKING_CILIUM_ALTERNATIVE.md): historical design context; the platform retains Flannel and the embedded K3s policy controller.
- [Workspace consolidation](LOCAL_WORKSPACE_REPORT.md): migration-specific tool/evidence locations. Current operator setup is in [runbook 11](../../runbooks/11-install-management-tools.md#operator-python-and-browser-tools).

- [Jenkins recovery and agent procedures](JENKINS_RECOVERY_RUNBOOKS_2026-10-25.md) — runbooks 22/23, reusable helpers and local checks.
