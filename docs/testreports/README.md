# Status and execution records

Start with the [implementation plan](IMPLEMENTATION_PLAN.md) for status and
remaining work. Read one [primary report](#phase-reports) per phase.
Reports describe dated executions, not current health.

For actions, use [runbooks](../../runbooks/README.md) and
[operations](../operations/README.md). Desired design is in
[architecture](../ARCHITECTURE.md). Follow the [documentation rules](../docs-structure.md).

## Phase reports

| Phase | Purpose | Primary report |
| --- | --- | --- |
| 00 | Baseline | [Report](phases/phase-00/REPORT.md) |
| 01 | Source import | [Report](phases/phase-01/REPORT.md) |
| 02 | Namespaces and credentials | [Report](phases/phase-02/REPORT.md) |
| 03 | DEV | [Report](phases/phase-03/REPORT.md) |
| 04 | STAGE and isolation | [Report](phases/phase-04/REPORT.md) |
| 05 | PROD | [Report](phases/phase-05/REPORT.md) |
| 06 | GitOps | [Report](phases/phase-06/REPORT.md) |
| 07 | Public access | [Report](phases/phase-07/REPORT.md) |
| 08 | Monitoring and private access | [Report](phases/phase-08/REPORT.md) |
| 09 | CI/CD ownership | [Report](phases/phase-09/REPORT.md) |
| 10 | CNPG, R2 and PITR | [Report](phases/phase-10/REPORT.md) |
| 11 | Certificates and refinement | [Report](phases/phase-11/REPORT.md) |

Each report links to its original execution and former planning notes under `history/`.

## Other records

- [Incidents](incidents/README.md): impact, diagnosis and recovery.
- [Decisions](decisions/README.md): accepted and superseded design choices.
- [Evidence](evidence/README.md): dated implementation records, screenshots and DR packages.
- [Archives](archive/README.md): prompts, retired plans and migration procedures.

## Preserved packages and scripts

- [DR evidence package](disaster-recovery-test/README.md): simulations and separate real local checks, including blocked R2/application recovery. Paths remain stable for original scripts and integrity records.
- [Application source archive](application-legacy-archive/README.md): old kind/Docker procedures and scripts. Source-relative references describe the original application revision.
- [Etcd-copy cleanup script](cleanup-etcd-recovery-copies-20261025.py): one-time cleanup retained at its original path; [execution record](evidence/records/2026-10-25-etcd-r2-backups.md#fixed-token-layout-and-scoped-cleanup).
- [Historical DR report pointer](DISASTER_RECOVERY_TEST_REPORT.md): retained for the recorded generator output path.

Reusable operator helpers remain in `scripts/` and are linked by current
manuals. No archived prompt or script grants authorization to execute it.
