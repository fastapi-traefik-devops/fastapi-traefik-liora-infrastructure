# Monitoring alert hardening — 2026-10-24

Status: **implemented and live-verified in NONPROD, then PROD**.

## Scope and result

All 55 originally loaded alert definitions were reviewed across the four native
platform/backup groups: selectors, real metric availability/labels, absence
behavior, scope, severity, hold durations, duplicate identities and routing.
Historical imported kind monitoring files were preserved and were not deployed.

The final inventory has **81 definitions / 40 distinct alert names**: NONPROD
28 platform + 15 backup; PROD 29 platform + 9 backup. Each cluster has 30 healthy
scrape targets. The final read-only audit found no firing or pending Prometheus
alerts, no rule evaluation errors and no source/live PrometheusRule mismatch.
The three known false backup telemetry alarms are cleared. No silences were
created or extended to achieve that result.

## Implemented changes

1. Coordinator ServiceMonitors preserve exported application namespaces with
   `honorLabels: true`. Actual ingested samples now match healthy, failure and
   overdue backup selectors for all environments.
2. Direct coordinator events include `prometheus=monitoring/monitoring-prometheus`,
   matching the external label on equivalent Prometheus notifications. FIRING
   and RESOLVED direct payload identity is covered by a local fixture. No new
   real backup failure was induced to test deduplication.
3. Add node capacity/accounting/request and missing-inventory guards, plus
   Pending/Failed application Pod signals and notification-delivery error guards.
4. Scrape the existing cert-manager metrics Service and add public app-tls
   readiness, missing telemetry and expiry diagnostics. No new monitoring
   workload or certificate controller was installed. These complement the
   owner's existing UptimeRobot checks; no external monitor was replaced.
5. Narrowly inhibit redundant collector/KSM observation alerts and lower-severity
   public expiry reminders. Independent full-backup failure/overdue, WAL failure/
   delay, cycle-blocked and PROD critical availability conditions stay visible.
   Testing-purpose alerts are excluded from all inhibition rules.
6. Slack titles show firing/resolved counts with a leading body separator;
   messages include source/runbook links where present. Cluster channel isolation,
   receiver Secret mounts, resolved notifications and hourly critical reminders
   are preserved. The 12h warning repeat policy is unchanged.

## Full configured-alert review

The definition count below includes distinct environment/cluster rules, not
just names. Original rules were retained where their behavior was intentional;
new rules fill demonstrated operational gaps without changing workload policy.

| Alert | Definitions | Review/action |
| --- | ---: | --- |
| `NodeMemoryPressure` | 2 | Retained Kubernetes pressure condition; supplemented with explicit capacity/accounting guards. |
| `NodeDiskPressure` | 2 | Retained sustained node condition; early PVC/filesystem thresholds remain a proposed extension. |
| `NodeHighCPU` | 2 | Retained 85% over 15m; evaluates the measured idle CPU rate. |
| `NodeHighMemory` | 2 | Retained guest available-memory signal; no longer treated as evidence of correct Kubernetes capacity. |
| `ApplicationRestartSpike` | 2 | Retained >=3 restarts in 15m, sustained 5m; scope limited to application namespaces. |
| `ApplicationDeploymentUnavailable` | 2 | Retained partial replica availability warning and intentional scale-to-zero behavior. |
| `ArgoApplicationUnhealthy` | 2 | Retained explicit environment/name scope and 10m delay. |
| `ArgoApplicationOutOfSync` | 2 | Retained independent GitOps drift signal and 10m delay. |
| `KubernetesNodeNotReady` | 2 | Retained false/unknown Ready handling; supplemented for missing Node objects. |
| `PrometheusTargetDown` | 2 | Retained multi-endpoint aggregation; narrow dependency inhibition only. |
| `PrometheusTargetMissing` | 2 | Extended expected-job inventory to coordinator and cert-manager. |
| `CertificateExpiringSoon` | 2 | Retained K3s remaining-lifetime seconds, <30d for 30m; not a public TLS metric. |
| `MonitoringMetricsMissing` | 2 | Extended to inputs required by new guards; kube-state-metrics warning cascade narrowly inhibited. |
| `NodeReadinessMetricMissing` | 2 | Retained known-node missing Ready-series detection. |
| `CertificateMetricMissing` | 2 | Retained reachable-API missing K3s certificate telemetry detection. |
| `NodeMemoryCapacityLow` | 2 | Added critical <7 GiB for 5m against the approved 8 GiB VM baseline. |
| `NodeMemoryAccountingMismatch` | 2 | Added critical >10% guest/Kubernetes capacity mismatch for 10m; exporter Pod mapped through kube_pod_info. |
| `NodeMemoryRequestsHigh` | 2 | Added regular-container requests >90% allocatable for 15m; explicitly a lower-bound scheduling signal. |
| `NodeCapacityMetricMissing` | 2 | Added missing per-node memory capacity/allocatable protection. |
| `ApplicationPodPending` | 2 | Added application Pending >10m to expose scheduling/admission/storage problems. |
| `ApplicationPodFailed` | 2 | Added Failed >5m, excluding ReplicaSet objects only when a fully available owning Deployment has replaced them. |
| `PrometheusNotificationDeliveryFailed` | 2 | Added sustained Prometheus-to-Alertmanager errors; no synthetic live failures induced. |
| `SlackNotificationDeliveryFailed` | 2 | Added sustained Slack-integration errors only, not unused integration counters. |
| `PublicCertificateNotReady` | 2 | Added app-tls Ready check; excludes CNPG internal certificates. |
| `PublicCertificateExpiringSoon` | 2 | Added <7d warning for 15m; complements existing UptimeRobot. |
| `PublicCertificateExpiryCritical` | 2 | Added <24h critical for 5m, including expired certificates; inhibits corresponding warning only. |
| `PublicCertificateMetricMissing` | 2 | Added expected per-environment Certificate missing telemetry check. |
| `KubernetesNodeInventoryIncomplete` | 2 | Added critical fewer than three observable nodes, including absent inventory. |
| `CNPGFullBackupFailed` | 3 | Corrected namespace ingestion; healthy/failure behavior tested in DEV/STAGE/PROD; direct-event identity aligned. |
| `CNPGFullBackupOverdue` | 3 | Corrected namespace ingestion; >26h comparison tested for every environment. |
| `CNPGBackupTelemetryMissing` | 3 | Corrected namespace ingestion; healthy samples no longer falsely appear absent. |
| `CNPGWALArchivingFailure` | 3 | Retained latest failure versus success ordering and independent PodMonitor scope. |
| `CNPGWALArchiveDelayed` | 3 | Retained pending-WAL requirement and 45m NONPROD / 10m PROD delay margins. |
| `CNPGWALTelemetryMissing` | 3 | Retained missing-primary telemetry protection; not suppressed by coordinator faults. |
| `R2BackupUsageHigh` | 1 | Retained informational 10 GiB warning; no quota/deletion behavior. |
| `R2BackupUsageTelemetryMissing` | 1 | Retained collection-failure/staleness checks; redundant only when collector itself is stale. |
| `CNPGBackupCollectorStale` | 2 | Retained >300s observation age plus 5m hold; used as narrow dependency root. |
| `ProductionDeploymentUnavailable` | 1 | Retained fail-closed critical behavior for zero availability or lost required metrics; not inhibited by exporter warnings. |
| `CNPGBackupCycleBlocked` | 1 | Retained fence/heartbeat protection and 2m hold; direct-event fingerprint aligned. |
| `CNPGBackupCycleTelemetryMissing` | 1 | Retained unknown Lease visibility signal; not confused with a known held cycle. |

## Local verification

- 23 backup/coordinator/metrics/PITR-safety/RPO-safety unit tests passed. They use
  fixtures; printed fixture failures are not live backup failures.
- Native backup rule syntax and healthy, failed, overdue and absent-data checks
  passed for each of DEV/STAGE/PROD, alongside firing/recovery fixtures.
- 72 routing cases passed with the native amtool, including cluster isolation,
  unknown labels and testing-route precedence.
- Platform rule syntax and behavior fixtures passed in both cluster variants:
  original missing-data/readiness/certificate/PROD-availability cases plus 14
  new memory, inventory, Pod, notification and public-certificate cases.
- The Failed-Pod refinement was tested with complete and incomplete replacements;
  standalone failures remain visible. There are 19 NONPROD and 22 PROD platform
  fixture cases in the combined validator.
- Native Alertmanager config and mixed FIRING/RESOLVED message rendering passed,
  including counts, whitespace, context and time fields. Inhibition guards assert
  that independent critical signals and testing alerts cannot be suppressed.
- The checksum-pinned kube-prometheus-stack 92.2.0 chart rendered the expected
  Alertmanager configuration and existing Secret mounts. amtool 0.34.1 was taken
  from the matching release archive after SHA-256 verification:
  `265b9d1e55ef0d5306a436018af6d2b686c2ce051f03d968f7464ecb1372a7e8`.
- All proposed expressions passed read-only live Prometheus query validation.
  A candidate join syntax error in the later Failed-Pod refinement was caught
  locally/read-only, corrected and retested before that refinement was applied.

Standalone validation entry points:
[Slack/rule/Helm validator](../../scripts/kubernetes/validate-slack-alerting.py),
[backup rule fixtures](../../scripts/backups/tests/check-rules.py), and
[read-only live audit](../../scripts/kubernetes/audit-monitoring-alerts.py).

## Live rollout and preservation

The existing chart/version was upgraded with reviewed values, `--skip-crds`,
`--wait` and a 10-minute bound: NONPROD Helm revision **4**, then PROD revision
**3**. The corresponding native rule and monitor files were applied; generated
operator output/Secrets were not edited manually. No chart default alert bundle
was enabled. The trusted cert-manager scrape endpoints preserve exported labels.

NONPROD passed before PROD activation: 43 rules, 30 targets and correct DEV/STAGE
namespace samples. PROD then loaded 38 rules and 30 targets with the correct
PROD namespace. New samples and configuration reloads required ordinary
reconciliation/scrape time; the initial immediate query was not treated as proof
of failure or readiness. Final native rule resources match source manifests.

Live validation surfaced a retained PROD backend Pod from October 23, rejected
with `OutOfmemory`, while its Deployment had 2/2 replicas available. The initial
new Failed-Pod guard could report that historical object. It was refined to
exclude only failed ReplicaSet Pods whose owning Deployment is fully available,
then retested and applied. The original Pod and its failure evidence were
preserved. A warning/resolution during this short rollout window is distinct
from a newly induced backend failure; no workload was killed or deleted.

VM 250's idle coordinator source was updated only for notification identity.
Runtime/source SHA-256 matched:
`421668f43f8a87831cfb66a10a4bc4744051fe3197677fa0b950efec5e59fb69`.
The old source remains `/opt/liora-backups/coordinator.py.before-alerting-20261024`.
The 02:00 UTC timer remains enabled/active; the completed cycle/fence was not
modified, and no backup was triggered. Metrics were not restarted unnecessarily.

All original monitoring Secret and PVC UIDs were preserved. No credential
provisioner or rotation was run. No application/database workload manifests were
edited/applied, and no application/database restart was requested. Jenkins jobs,
polling, publisher definitions, routing, DNS and public certificate ownership
were not changed by this work. All five Argo Applications remained Synced/Healthy.
Independent concurrent recovery evidence and documentation commits were merged
normally with `3ddc77b`, without rewriting history or replacing their contents.

## Delivery evidence and limits

Earlier actual Slack receipt in both normal channels remains verified by the
owner's supplied history in
[the alerting review](BACKUP_ALERTING_REVIEW_2026-10-24.md). After this rollout,
Prometheus and Alertmanager no longer show the three false telemetry alarms.
Notification counters were inspected: no new Slack failures or Prometheus
notification errors were observed in the checked 10-minute windows. Effective
configs use the new titles and the same normal/testing receivers; NONPROD has
four reviewed inhibition rules and PROD five.

No arbitrary new Slack message or synthetic live failure was sent. Transport
counters and cleared API state do not independently prove a person received the
post-change RESOLVED messages; that confirmation was requested from the owner
and remains outstanding unless subsequently recorded. All newly added failure
scenarios are fixture-tested, not claimed as real incident delivery tests.

## Operator recheck and rollback

From the original checkout with the existing private kubeconfigs:

```sh
bash scripts/local-python.sh scripts/kubernetes/audit-monitoring-alerts.py --output .local-work/private/alerting-audit.json
```

[Standalone audit script](../../scripts/kubernetes/audit-monitoring-alerts.py).
It uses bounded GET/query requests and reads only native PrometheusRule resources
through kubectl; it never fetches Secrets or receiver configurations. A nonzero
result means an active/pending condition, rule/source mismatch, scrape problem
or failed audit needs inspection. Do not automatically silence such a result.
Queries and actual loaded rules/labels are retained in the JSON evidence.

If configuration rollback is necessary, use the saved private pre-upgrade Helm
values and the previous reviewed native manifests. Preserve existing Secret/PVC
identities and verify effective routing after reload. Do not blindly undo the
coordinator `honorLabels` correction: that reintroduces the known false alarms
and failure/overdue blind spot. Restore only the faulty change after review.
The previous Helm revisions are NONPROD 3 and PROD 2. A code rollback on VM 250
can restore the saved source while its coordinator is idle; preserve the cycle
Lease and timer state. No rollback was needed or executed here.

## Remaining improvements offered, not applied

1. **Persist the approved VM memory policy in IaC.** Terraform still defaults to
   maximum 8192 MiB and `memory_min_mb=2048`, passed as ballooning `floating`.
   Existing private overrides may differ. Compare the owner's corrected VM
   settings against those overrides before another infrastructure apply; source
   defaults alone do not preserve the manual fix. No Terraform/VM change was
   made as part of alerting work.
2. **Early PVC/filesystem capacity and PROD standby/lag guards.** Suitable source
   metrics exist: kubelet volume stats (16 series NONPROD, 8 PROD), root filesystem
   availability (three per cluster), and CNPG replication lag. Existing root
   filesystems had approximately 89%/92% minimum available space. Choose per-PVC
   thresholds and replication expectations deliberately; no invented unsupported
   metric or one-size storage policy was deployed. Guest volume space also does
   not establish Proxmox/ZFS thin-storage headroom.
3. **Independent monitoring-path heartbeat.** Existing UptimeRobot application/
   certificate monitoring is not proof that Prometheus/Alertmanager/Slack can
   notify while that path is down. A separate heartbeat/secondary notification
   path is a future integration; SMTP remains deferred. Private admin endpoints
   need not be exposed to implement an outbound heartbeat.
4. **Longer forensic evidence when justified.** Current Prometheus retention is
   3d, and rotated controller logs limited this incident's root-cause certainty.
   Preserve incident snapshots promptly; agree storage/resource budgets before
   increasing retention or implementing the separately planned logging stack.
5. **Meaningful external application checks.** Confirm the existing DEV/STAGE
   external checks distinguish application behavior from a Cloudflare Access
   login/redirect response. Provider configuration and receipt were not accessed
   or changed by this task.

Primary semantics references:
[Prometheus honor_labels](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config),
[Prometheus Operator Endpoint API](https://prometheus-operator.dev/docs/api-reference/api/#monitoring.coreos.com/v1.Endpoint).

## Evidence and commits

Private records are in `.local-work/private/alerting-2026-10-24/`: saved Helm
values, Secret/PVC UID baselines, rollout logs, rule-test logs, initial/final
read-only audits and delivery/preservation checks. No webhook, token or private
configuration values were printed or committed. Public reports contain only
sanitized findings and source/runtime identifiers.

Implementation: `dfcdd63` (labels/identity), `789741c` (coverage/routing),
`5f11e41` (replacement-aware Failed-Pod refinement). This report and the audit
helper are committed separately with final operational evidence.
