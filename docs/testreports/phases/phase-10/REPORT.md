# Phase 10 — PostgreSQL and recovery

Summary as of 2026-10-25. Environment: DEV, STAGE and PROD.

## Result

| Checkpoint | Implemented | Recorded verification |
| --- | --- | --- |
| 10.1: fresh CNPG databases | Separate PostgreSQL 16 databases; PROD async primary/standby on different nodes | Existing-image login/CRUD, stable endpoint and replication passed on 2026-10-23. No old-data migration was performed. |
| 10.2: physical backups and PITR | R2 base backups/WAL, retention, coordinator and alerts | Isolated target inclusion/exclusion and restored application checks passed on 2026-10-23. |

| Environment | Recorded PITR application usability | Natural WAL delivery |
| --- | --- | --- |
| DEV | 286.163 s | 303.059 s |
| STAGE | 195.483 s | 304.031 s |
| PROD | 287.029 s | 304.043 s |

Source: [10.1 execution](history/cnpg-installation-2026-10-23.md) and
[10.2 execution](history/r2-backup-pitr-2026-10-23.md).
The earlier 10.1 statement that backups were pending predates 10.2.

## Limits and remaining work

- PITR timings exclude infrastructure rebuild. They do not prove full-system recovery.
- Full 7/14-day coverage needs elapsed retention history and repeated verification.
- Bucket-policy metadata returned 403; the recorded object-operation checks do not audit that policy.
- Live database cutover, etcd restore, off-host kit retrieval and full-system DR remain separate verification tasks.
- Repeat isolated PITR monthly and after backup mechanism changes.

The [local DR follow-up](../../disaster-recovery-test/README.md) retained blocked
R2/application recovery checks. It does not undo the earlier isolated PITR result
or establish an independent full recovery.

## References

- [Former plan and execution notes](history/plan-notes-2026-10-25.md)
- [Current remaining work](../../IMPLEMENTATION_PLAN.md#recovery-and-operational-follow-up)
- [Backup operations](../../../../runbooks/19-cnpg-r2-backup-pitr.md)
- [Recurring recovery verification](../../../operations/POSTGRESQL_BACKUP_VERIFICATION.md)
