# Grafana verification — 2026-10-23

Environment: NONPROD (DEV/STAGE) and PROD. Method: recorded live queries and
browser captures. Purpose: verify Operations dashboards and environment filters.

Report: [dashboard execution](../../archive/migration-procedures/phase8-grafana-execution-archive.md).
Structured results and original image SHA-256 values:
[verification JSON](../grafana-operations-validation.json).
Current procedure: [Grafana operations](../../../operations/GRAFANA_OPERATIONS_DASHBOARDS.md).

| NONPROD image | PROD image | Establishes |
| --- | --- | --- |
| [Operations](nonprod-operations.png) | [Operations](prod-operations.png) | Recorded application/cluster overview rendering. |
| [Capacity](nonprod-capacity.png) | [Capacity](prod-capacity.png) | Recorded node and namespace capacity panels. |
| [Assurance](nonprod-assurance.png) | [Assurance](prod-assurance.png) | Dashboard coverage and instrumentation limits at capture time. |

The record reports 140 NONPROD and 79 PROD query variants checked. It also
records `CNPGBackupTelemetryMissing`: two NONPROD alerts and one PROD alert.
These failures are retained. Later [alert corrections](../records/2026-10-24-alerting-optimization.md)
are separate evidence. These images do not prove current health, SQL readiness,
backup success or disaster recovery.
