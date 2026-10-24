# Backup alerting and Slack delivery review — 2026-10-24

Status at the original review: **real Slack delivery confirmed; a live rule/label defect remained**.
Read-only review at approximately 13:02–13:04 UTC, after
[the blocked-cycle recovery](BACKUP_INCIDENT_2026-10-24.md).
No alert rules, scrape settings, receivers, credentials, silences or live
workloads were changed by this review.

**Subsequent authorized remediation:** the label/identity issues were corrected,
coverage and routing hardened, and both clusters live-verified later the same
day. See [the implementation report](ALERTING_OPTIMIZATION_2026-10-24.md). The
observations and unapplied proposals below retain their original review context.

## Verified operational facts

The owner supplied actual FastAPI Monitoring messages received in
`#liora-alerts-nonprod` and `#liora-alerts-prod` on October 23–24. These establish
real delivery of backup/WAL alerts to the normal operational channels, beyond
the earlier synthetic tests in `#liora-alerts-testing`.

Confirmed by the supplied Slack messages:

- Backup telemetry FIRING notifications reached both normal channels.
- WAL telemetry FIRING and RESOLVED notifications reached both clusters'
  normal channels.
- The actual blocked backup cycle generated PROD FIRING notifications.
- Platform target/Argo/deployment notifications and resolutions were delivered.

Live inspection also confirmed that both Alertmanagers route their own cluster
to the expected normal receiver with `send_resolved: true`. Prometheus had all
15 NONPROD and 9 PROD backup rules loaded with evaluation health `ok` and no
evaluation errors. All 29 discovered scrape targets per cluster were healthy.

**This proves notification delivery and operation of the observed conditions,
not correctness of every backup rule.** No real failed-upload, full-backup-overdue
or high-R2-usage delivery was established by these messages. Rule evaluation
health alone does not prove a selector matches the intended metric series.
Slack receipt of the blocked cycle's post-recovery RESOLVED message was not
provided; the live blocked condition itself was already inactive.

## Why alerts repeated

The effective critical route uses `repeat_interval: 1h`, `group_interval: 5m`
and `group_wait: 30s`. Repeated messages with the same Started timestamp are
reminders of an ongoing alert, not proof of a new failed backup every hour.
Actual delivery spacing in the supplied history was often about 65 minutes;
the read-only review did not trace every notification's scheduling latency.
Warning routes inherit a 12-hour repeat interval from the root route.

Slack's displayed message time and the explicit UTC Started/Resolved fields
are different references. In particular, the last supplied blocked-cycle
message at 14:19 local time precedes the 12:56 UTC recovery when the display
uses UTC+2. Do not interpret that message as a new post-recovery failure.

An overall FIRING heading can contain both FIRING and RESOLVED entries when
different instances in one alert group have different states. That is not by
itself contradictory; read the per-alert instance and state.

## Meaning and interpretation of the supplied alerts

| Alert | Meaning | Interpretation here |
| --- | --- | --- |
| `CNPGBackupTelemetryMissing` | The rule cannot find healthy per-environment coordinator telemetry | Currently a false positive for all three environments because of the label collision below; these messages do not prove R2 or Backup API failure |
| `CNPGWALTelemetryMissing` | Primary WAL archive metrics are absent | Loss of visibility, not proof that WAL upload failed; STAGE's disappearance overlaps the known database/admission incident and recovered around 07:01 UTC |
| `CNPGBackupCycleTelemetryMissing` | VM 250 cannot observe the global PROD Lease, or that metric is absent | Consistent with the PROD API/scrape disruption in the supplied history; now inactive and the metric is healthy |
| `CNPGBackupCycleBlocked` | A retained cycle is blocked or its owner heartbeat stopped | Real incident: the coordinator timed out at 04:00 UTC waiting for STAGE; cleared after explicit resume at 12:56 UTC |
| `PrometheusTargetDown` | A discovered endpoint cannot be scraped for five minutes | Real scrape failures; could reflect Pod/node/API/network disruption, not necessarily failure of the monitored business service |
| `PrometheusTargetMissing` | An expected job disappeared from discovery | Missing monitoring coverage; not proof of application loss by itself |
| `ArgoApplicationUnhealthy` | Argo reports DEV/STAGE unhealthy | STAGE was unhealthy during the known database problem; supplied resolution at 07:02 UTC matches recovery |
| `ProductionDeploymentUnavailable` | Required deployment has no available replicas, or required deployment metrics disappeared | Critical protection worked, but simultaneous kube-state-metrics loss means this alert alone cannot establish an actual frontend/backend outage |
| `MonitoringMetricsMissing` | A platform rule's required metric is absent | Explains uncertainty in deployment/node/restart alerts during exporter/API disruption |
| `ApplicationRestartSpike` | A container restarted at least three times in 15 minutes | PROD frontend instability was observed; this message alone does not identify OOM, resource admission or another restart cause |

The historical memory-accounting fault and STAGE Pod admission rejections are
documented in the incident report. They establish a real infrastructure problem,
but should not be used to assign every alert to memory without separate evidence.

## Confirmed defect: exported namespace conflicts with scrape namespace

VM 250 correctly emits per-environment metrics with labels such as:

```text
liora_backup_telemetry_ok{cluster="nonprod",environment="DEV",namespace="app-dev"} 1
```

The `backup-coordinator` ServiceMonitor/Service lives in `monitoring`. Its
endpoint does not set `honorLabels: true`. In the actual Prometheus samples,
the scrape's namespace wins and the original namespace becomes:

```text
namespace="monitoring", exported_namespace="app-dev"
```

The same happens to STAGE and PROD. Current rules filter on
`namespace="app-dev"`, `app-stage` or `app-prod`, so their matching series are
empty even though VM 250 reports `telemetry_ok=1` and the target is up.

Read-only query evidence:

```promql
absent(liora_backup_telemetry_ok{environment="DEV",namespace="app-dev"})
# Returns 1: the current rule considers the intended series missing.

max(liora_backup_telemetry_ok{environment="DEV",exported_namespace="app-dev"})
# Returns 1: the actual exporter observation is healthy.

liora_backup_last_success_timestamp{environment="DEV",namespace="app-dev"}
# Returns no series despite the completed DEV backup.
```

The equivalent PROD checks returned the same results. All three environment
telemetry values were healthy in their real ingested series.

Consequences:

1. `CNPGBackupTelemetryMissing` keeps firing falsely after backup recovery.
2. `CNPGFullBackupFailed` and `CNPGFullBackupOverdue` also use the mismatched
   namespace filter. Their empty-vector comparisons do not raise the intended
   failed/overdue alarms. This is a coverage defect, not just noisy Slack.
3. The global cycle metrics have no exported application namespace and are not
   affected by this particular collision. WAL metrics use their separate CNPG
   PodMonitor path; do not apply a blanket namespace change to those rules.

The collision explains the continuing telemetry notifications independently of
the real resource incident. Some historical messages may coincide with actual
API failures, but this rule cannot distinguish those from its selector defect.

## Current state after backup recovery

At review time:

- NONPROD: exactly two Prometheus firing alerts, the false DEV/STAGE
  `CNPGBackupTelemetryMissing` instances.
- PROD: exactly one firing alert, the false PROD `CNPGBackupTelemetryMissing`.
- The same three alerts were active in Alertmanager without silences/inhibition.
- Coordinator target up in both clusters; all 58 discovered targets healthy.
- All three actual backup telemetry values were 1. Global telemetry was 1 and
  cycle-blocked was 0. CycleBlocked and WAL-telemetry rules were inactive.
- Physical backups had completed and the existing daily schedule was restored,
  as recorded in the incident report. Persisting telemetry alarms do not mean
  that the coordinator recovery failed.

## Recommended follow-up, not applied by this review

### Priority 1: repair label handling and test the whole scrape/rule path

The smallest proposed change is `honorLabels: true` on only the coordinator
ServiceMonitor endpoint in each cluster. That preserves the controlled exporter's
application namespace labels without changing other scrape jobs or the backup
mechanism. Live Prometheus did not set `overrideHonorLabels` or
`enforcedNamespaceLabel`, so neither currently blocks that approach.

An alternative is to adapt coordinator-rule selectors to `exported_namespace`,
but that couples the rules to the scrape collision. Do not apply both remedies
indiscriminately or change unrelated PodMonitor namespace handling.

Before deployment, add a meaningful fixture/check covering the actual ingested
label set, healthy absence behavior, full-backup failure and overdue conditions.
After deployment, inspect live samples, evaluate all three environment rules,
wait through evaluation/notification intervals, and verify the three false
alarms resolve in Slack. Do not deliberately break live databases/backups to
test this; use fixtures and separately identified notification tests if needed.
This review does not claim those follow-up tests or resolutions have happened.

### Priority 2: detect the memory-accounting incident earlier

Add monitoring for unexpected node capacity/allocatable reduction compared with
the configured VM baseline, and allocated/requested memory relative to that
capacity. Correlate with Pod admission failures/Pending/Failed status.
Guest RAM availability, `MemoryPressure` and OOM-kill counters alone did not
detect or explain this particular failure mode adequately.

### Optional noise and presentation improvements

- Keep hourly critical reminders initially; suppressing or lengthening repeats
  does not fix the selector defect. Choose a longer interval later only as an
  explicit operational preference.
- Consider narrowly scoped inhibition of redundant coordinator telemetry alerts
  while that specific exporter is down/stale. Keep independent backup failure,
  overdue, WAL and global-fence conditions visible. Existing inhibition does not
  currently cover this dependency.
- Improve annotations to distinguish missing samples from `telemetry_ok=0`, and
  make the root-cause checks more specific. Fix concatenated Slack title/body
  text separately as presentation work if desired.
- Review deduplication between the coordinator's direct Alertmanager events and
  the equivalent Prometheus rules. The direct client does not include the
  `prometheus` label seen on actual Prometheus-delivered alerts, so identical
  alert names do not guarantee identical Alertmanager fingerprints. Harmonize
  the intended label sets deliberately; do not remove a safety path merely to
  reduce messages. The closely spaced historical CycleBlocked messages were
  not traced to individual fingerprints by this review.
- Add direct report/runbook links to alert actions. Do not silence all backup
  alarms or clear a held cycle to make the channel quiet.

No new monitoring architecture or backup implementation is needed. Delivery is
verified; label handling requires correction before calling all backup alarm
coverage correct. Full restore/PITR guarantees are not established by Slack
messages and remain subject to their separate recovery evidence/exercises.

Private read-only API evidence is retained at
`.local-work/private/incidents/2026-10-24-backup/alerting-review.json`.
Webhook URLs, Secret contents and complete Alertmanager configurations were
not printed or committed. Slack delivery evidence is the owner's supplied
message history; no new Slack message was sent by this review.
