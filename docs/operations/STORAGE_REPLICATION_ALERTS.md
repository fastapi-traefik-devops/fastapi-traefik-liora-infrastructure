# PVC filesystem and PROD replication alerts

These rules use existing kubelet and CloudNativePG metrics. They do not resize
volumes, change replication, or perform automatic recovery.

| Condition | Warning | Critical |
|---|---|---|
| Backing filesystem available bytes | Below 20% for 15 minutes | Below 10% for 5 minutes |
| Backing filesystem free inodes | Below 10% for 15 minutes | Below 5% for 5 minutes |
| Mounted Bound filesystem PVC telemetry incomplete | 15 minutes | — |
| PROD standby unavailable or not streaming | — | 5 minutes |
| PROD standby replay lag | Above 60 seconds for 5 minutes | Above 300 seconds for 5 minutes |
| Reachable PROD exporter missing replication query results | 5 minutes | — |

## Filesystem interpretation and response

The current local-path volumes share their node filesystem. Kubelet reports that
filesystem's capacity and free space; a PVC request is not an enforced directory
quota. Never divide these filesystem usage metrics by the requested PVC size.
Pressure alerts aggregate by node, avoiding duplicate notifications for claims
sharing the filesystem. Byte and inode pressure remain independent conditions.

Only `job="kubelet",metrics_path="/metrics"` samples with a node label are used.
K3s also exposes duplicate volume metrics through the apiserver scrape; those
samples have different namespace semantics and are excluded.

`PVCFilesystemTelemetryMissing` checks valid byte and inode samples for Bound
filesystem claims referenced by Running Pods. Known raw Block volumes and
retained claims without Running Pods are excluded. Missing, invalid or NaN
telemetry is not evidence of sufficient free space. Missing KSM inventory inputs
are covered separately by `MonitoringMetricsMissing`.

- [ ] Inspect the named node, its filesystem capacity/inodes, mounted PVCs, logs and retention before choosing remediation.

Do not delete database files or unrelated PVCs. Increasing a local-path PVC request alone does not increase the backing
filesystem. Proxmox/ZFS pool capacity is a separate monitoring concern.

## PROD standby interpretation and response

The desired cluster has one primary and one asynchronous standby. Availability
requires exactly one observable standby with a WAL receiver, and at least one
streaming connection reported by an observable primary. SQL recovery state,
collector health and scrape health are matched by namespace, Pod and instance;
Pod names and exporter role labels do not determine the primary.

Lag thresholds apply only to observable standbys. The installed CNPG query
returns zero for an idle caught-up replica when receive/replay LSNs match. A
receiver disconnected after catching up can also have zero replay lag, so the
separate availability rule remains essential. Missing or invalid query metrics
raise a telemetry warning. These checks do not establish an RPO or verify backup
restorability.

- [ ] Inspect CNPG Cluster status, Pod placement/events, receiver and primary streaming state, storage and resource pressure.

Follow the database runbooks before any repair. Do not promote a standby, reset a database, or delete a PVC solely to
clear an alert.

Critical pressure/lag inhibits only its corresponding warning for the same
node or Pod. Standby unavailability inhibits the subordinate replication-query
telemetry warning in app-prod. Independent critical database, backup and WAL
alerts remain enabled. Test-purpose alerts are excluded from inhibition.

## Read-only verification

**Where:** Infrastructure checkout with explicit administrator kubeconfigs.

- [ ] Run the read-only audit:

```sh
bash scripts/local-python.sh scripts/kubernetes/audit-monitoring-alerts.py \
  --cluster both --output .local-work/private/storage-replication-audit.json
```

The audit compares Git rule specifications with cluster resources, checks loaded
rule health and scrape targets, and records relevant metrics and active alerts.
Its nonzero status requires investigation; it does not modify resources.
Use [alert configuration validation](SLACK_ALERTING.md#2-validate-and-reconcile-configuration) before changing thresholds or inhibition.

**Done when:** The affected filesystem or replica condition is corrected, telemetry is present, and the matching alert resolves.
