# Early PVC filesystem and PROD replication alerts — 2026-10-24

## Scope

Follow-up to [alerting hardening](2026-10-24-alerting-optimization.md), implementing
its second proposed improvement. Existing metrics supply the new alerts; no
storage size, database configuration, replication mode or application image was
changed by this work. No live failure, failover or host-reboot test was performed.

## Design and evidence

- Kubelet volume statistics describe the shared approximately 197 GiB node
  filesystem, rather than the requested 2 GiB database PVC quota. Byte/inode
  pressure is grouped by node, using canonical kubelet `/metrics` samples only.
  Duplicate K3s apiserver samples are excluded. Requested PVC size is not used as
  a denominator. This is not Proxmox/ZFS pool monitoring or quota enforcement.
- Byte warning/critical thresholds: available space below 20% for 15 minutes /
  below 10% for 5 minutes. Inode warning/critical thresholds: below 10% for
  15 minutes / below 5% for 5 minutes.
- Missing/invalid byte or inode telemetry on a mounted Bound filesystem claim
  warns after 15 minutes. Unmounted retained claims and known raw Block claims
  are excluded. Missing inventory families have independent guards.
- PROD expects one observable streaming standby and an observable primary
  reporting at least one streaming connection. Missing/disconnected standby
  becomes critical after 5 minutes. Coherent SQL role, collector and scrape
  samples are joined by namespace/Pod/instance, allowing role changes.
- Standby replay lag above 60 seconds warns after 5 minutes; above 300 seconds
  becomes critical after 5 minutes. Missing/invalid replication-query telemetry
  warns after 5 minutes. Idle caught-up replicas correctly report zero in the
  installed CNPG LSN-aware query; a disconnected receiver can also show zero,
  hence independent streaming availability checks are required.
- Critical pressure/lag inhibits only the corresponding warning for the same
  node/Pod. Standby unavailability inhibits its subordinate telemetry warning.
  Independent backup, WAL and critical replication signals remain enabled.

These alert thresholds do not guarantee an application RPO or prove backup
restorability. The current asynchronous replication mode is unchanged.

## Local validation

The pinned validator passed for NONPROD and PROD: configuration syntax,
36 routing cases per cluster, FIRING/RESOLVED templates, rule syntax/behavior,
Helm rendering and webhook Secret mounting. The 27 new regression scenarios
include shared filesystems, duplicate apiserver samples, claim sizes, missing/
invalid/NaN metrics, inode exhaustion, retained/Block claims, namespace isolation,
critical hold/recovery timing, healthy idle replicas, receiver/primary connection
loss, high/critical lag, missing collectors, role changes and excess standbys.
Fourteen storage scenarios run in each cluster; thirteen replication scenarios
run only for PROD. Existing alert behavior fixtures run alongside these cases.

All 14 new expressions were also evaluated against live Prometheus before
installation and returned no active condition. Fixtures simulate faults locally;
no incident-channel failure injection or live database disruption was required.

Operator guidance: [storage and replication alerts](../../../operations/STORAGE_REPLICATION_ALERTS.md).
Source changes: `7ad9ebc`; concurrent STAGE promotion history was preserved when
integrating the monitoring commit.

## Live rollout and final acceptance

Applied NONPROD first, then PROD after its predecessor passed. The pinned
kube-prometheus-stack 92.2.0 chart remains unchanged; monitoring Helm releases
are deployed at NONPROD revision 5 and PROD revision 4. Existing runtime
components were reused, with no new exporter or workload installed.

The final source/live audit completed at **15:05:18–15:05:20 UTC**:

| Check | NONPROD | PROD |
|---|---:|---:|
| Healthy loaded alert definitions | 48 | 47 |
| Healthy scrape targets | 30 | 30 |
| Firing/pending alerts | 0 | 0 |
| Source/live rule mismatches or evaluation errors | 0 | 0 |
| Loaded inhibition rules matching source | 6 | 9 |
| Protected existing identities checked, unchanged | 78 | 52 |

The protected identity checks cover all original Secrets/PVCs and the original
database/Jenkins Pods. The PROD primary `liora-db-1` remains on `k3s-2-02`, and
standby `liora-db-2` remains on `k3s-2-03`; both database Pods are 2/2 ready.
Recorded SQL telemetry: primary recovery=0, streaming_replicas=1; standby
recovery=1, receiver_up=1, replay lag=0 seconds. No data or replica configuration
change was needed. Both Kustomize renders include their new native rule groups.

Immediately after apply, the audit correctly reported rule groups not yet
reloaded, followed briefly by new rules whose first evaluation had not run.
Those cleared after normal operator/config-reloader convergence. Concurrent
STAGE promotion also produced transient Pending/OutOfSync/Unhealthy observation;
STAGE returned Healthy/Synced, without suppressing or changing those alerts.
The final audit passed for both clusters. No silence was used to hide conditions.

The previous review remains historical evidence for its 81-definition inventory;
this follow-up brings the inventory to **95 definitions / 49 distinct names**.
Existing backup schedules, notification routes and application/DB settings were
not edited. No new Slack incident was injected; local routing/template tests and
loaded Alertmanager inhibition comparisons verify this change's configuration.
The earlier owner-confirmed Slack delivery evidence remains in the hardening
report. This change does not claim a new real failure notification exercise.

Private evidence is retained under
`.local-work/private/storage-replication-2026-10-24/`: validation logs,
preflight expression results, Helm logs, intermediate/final audits, metadata-only
identity baselines and preservation comparisons, and Kustomize renders.
No private recovery inputs or credentials were added to Git.

## Remaining boundaries

This completes the proposed early PVC-space and PROD standby/lag alert addition.
Proxmox/ZFS capacity, VM memory policy review and an external monitoring watchdog
remain separate proposals. Monthly PITR and the separately delegated Phase 9
work are not completed by these alert checks.
