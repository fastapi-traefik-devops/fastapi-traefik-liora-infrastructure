# Liora Slack alerting

## Status and ownership

Deployed on **2026-10-23** after explicit user approval: NONPROD Helm revision
**3**, then PROD revision **2** after NONPROD review. Both clusters loaded the
expected routing and healthy alert inventory (15 NONPROD / 16 PROD).
**FIRING and RESOLVED delivery to `#liora-alerts-testing` was confirmed by the
user for both clusters.** Existing credential Secrets were preserved. See the
[deployment evidence and rollback record](SLACK_ALERTING_DEPLOYMENT_2026-10-23.md).
The commands below remain the procedure for future installations and changes;
another deployment still requires review and approval.

Initial read-only inspection reached both live clusters through the management server
(`ssh root-admin@liora.aprt.info -p22100`). Each effective Alertmanager config
still used `pending-destination`, matching Git; neither monitoring namespace had
a Slack-named Secret. All eight original alerts were loaded with `health: ok`.
This is a point-in-time observation: inspect again immediately before rollout
and preserve any intervening working configuration.

Helm owns each independent `monitoring` release. The Prometheus Operator manages
its generated workloads and configuration. The monitoring kustomizations own
additional rules, monitors, dashboards and VIP Services. Do not edit generated
Secrets, StatefulSets or operator output, or add a competing Argo CD Application.
The `upstream/monitoring` snapshot and application repository's `monitoring/`
directory describe the historical kind installation; they are not K3s rollout
inputs. See [the existing Helm runbook](../../runbooks/16-private-platform-access.md).

| Cluster | Environments | Private VIP | Explicit kubeconfig | Normal Slack channel |
| --- | --- | --- | --- | --- |
| NONPROD | DEV, STAGE; shared platform | 192.168.77.16 | `$HOME/.kube/config-dev-stage` | `#liora-alerts-nonprod` |
| PROD | PROD | 192.168.77.17 | `$HOME/.kube/config-prod` | `#liora-alerts-prod` |

Each cluster has its own Prometheus (:9090), Alertmanager (:9093), storage,
Secrets and Helm release. Both use the **FastAPI DevOps** Slack workspace.
Slack is reached outbound over HTTPS; monitoring endpoints remain private.
The server's default kubeconfig points to an unreachable legacy kind cluster:
always use the explicit kubeconfigs above.

## Routing and message format

Routing first checks the exact cluster label. Mismatched or missing cluster
labels go to the empty `discard` receiver, preventing cross-cluster routing.
Prometheus external labels and every platform rule provide the correct cluster.
Direct Alertmanager API clients must include it themselves.

Within that cluster, the **first** child route matches `purpose="test"` and sends
only to `#liora-alerts-testing`, regardless of severity. It does not continue to
incident routes. The test route groups by cluster, alert name and unique test
ID, waits 10 seconds, updates every 30 seconds, and repeats after one hour.
Tests without the correct label are unsafe; use the supplied helper.

Critical alerts stay in their cluster's normal channel with a 30-second wait,
five-minute update interval and one-hour repeat. Warnings use a one-minute wait,
five-minute update interval and 12-hour repeat. Other non-test severities use
the same cluster-local fallback. PROD warnings never go to NONPROD. Normal groups
include cluster, environment, severity, alert name, namespace and purpose.

Messages contain cluster identity fixed by the receiving configuration, per-alert
status, environment, severity, alert name, available namespace/resource labels,
description, suggested diagnostic action, UTC start time and UTC recovery time.
DEV/STAGE are explicit rule labels or derived from exact namespace/application
names. Shared NONPROD node and exporter alerts use `PLATFORM`; PROD rules use
`PROD`. Optional runbook links are displayed when provided. Both Slack receivers
set `send_resolved: true`.

PROD's critical deployment alert inhibits the original deployment warning for
the same cluster, namespace and deployment while the critical alert is firing.
Tests are excluded from this inhibition. Chart default inhibition rules and
template-file defaults are explicitly replaced so Helm cannot silently add them.

## Alert inventory

The original eight expressions, thresholds, durations and severities are preserved;
environment labels, descriptions and diagnostic actions were added.

| Alert | Severity | Trigger / pending duration |
| --- | --- | --- |
| NodeMemoryPressure | warning | Kubernetes MemoryPressure true / 5m |
| NodeDiskPressure | warning | Kubernetes DiskPressure true / 5m |
| NodeHighCPU | warning | CPU usage >85% / 15m |
| NodeHighMemory | warning | Memory usage >90% / 15m |
| ApplicationRestartSpike | warning | At least 3 restarts in 15m / 5m |
| ApplicationDeploymentUnavailable | warning | Available replicas below desired / 10m |
| ArgoApplicationUnhealthy | warning | Environment application not Healthy / 10m |
| ArgoApplicationOutOfSync | warning | Environment application not Synced / 10m |
| KubernetesNodeNotReady | critical | Ready=true gauge is zero (false or unknown) / 5m |
| PrometheusTargetDown | warning | Any discovered endpoint fails, aggregated by job/instance/namespace/service / 5m |
| PrometheusTargetMissing | warning | Any of 12 verified jobs disappears entirely / 10m |
| CertificateExpiringSoon | warning | K3s certificate remaining lifetime <30 days, including expired / 30m |
| MonitoringMetricsMissing | warning | Required alert metric family or expected Argo application series absent / 10m |
| NodeReadinessMetricMissing | warning | Known node lacks its Ready condition series / 10m |
| CertificateMetricMissing | warning | Reachable API instance lacks certificate metrics / 1h |
| ProductionDeploymentUnavailable (PROD only) | critical | Required backend/frontend has zero available replicas with desired >0, missing availability metrics, or missing desired-replica metrics / 5m |

Totals after deployment: **15 NONPROD / 16 PROD** alerts. Adminer remains covered
by the original warning; the PROD critical outage rule targets backend/frontend.
Partial replica loss keeps the warning, avoiding a second critical alert for it.
Intentional scale-to-zero does not trigger the critical rule while its metrics exist.

Live Prometheus 3.15.0 exposed all metrics used by these additions. All 15 new
expression evaluations (seven NONPROD, eight PROD) succeeded against the respective
live instances and returned no active series at inspection time. These were
read-only queries, not installation of the new rules.

`k3s_certificate_expiration_seconds` measures **remaining lifetime**, not a Unix
timestamp. The rule uses `job="apiserver"` to avoid counting the same K3s
certificate through several embedded component endpoints. Its scope is internal
K3s certificates, not the public website/edge TLS certificate.

**BackupFailedOrStale is deferred.** No CNPG/Barman backup success, failure or
last-success timestamp metrics were exposed. K3s snapshot duration histograms
exist, but duration/count alone does not prove backup success, off-host storage,
freshness or restoreability. First define the database/etcd backup schedules,
enable supported backup telemetry, verify actual metric semantics in each cluster,
then add critical failure/staleness and missing-telemetry checks with tested
schedule margins. No unsupported backup metric or assumed schedule is used here.

## Slack application and secure credentials

1. In the **FastAPI DevOps** workspace, open the existing **FastAPI Monitoring**
   app in [Slack app management](https://api.slack.com/apps). Verify that you have
   permission to manage it; enable Incoming Webhooks if needed.
2. Inspect its existing webhook entries and channel bindings. Renaming a channel
   may leave the existing channel identity usable, but verify the current binding
   and app membership. Neither cluster currently has credentials proving reuse.
3. Reuse correctly bound entries or choose **Add New Webhook to Workspace**.
   Authorize a NONPROD normal webhook for `#liora-alerts-nonprod`, a PROD normal
   webhook for `#liora-alerts-prod`, and separate testing webhooks for each cluster
   bound to `#liora-alerts-testing` (four URLs recommended for independent rotation).
4. An incoming webhook is bound to its authorized channel. The YAML `channel`
   field cannot retarget modern Slack app webhooks. Do not put a PROD webhook
   into a NONPROD or testing Secret slot. Verify bindings in Slack before testing.
5. Keep URLs in a password manager and enter them only at the helper's hidden
   prompts in an interactive terminal. Never paste them into chat, shell command
   arguments/history, files in Git, screenshots, logs or reports. Do not use `set -x`.

After explicit approval to create Secrets, from the infrastructure checkout on
the management server (Python 3 and PyYAML required):

```sh
python3 scripts/kubernetes/create-slack-secret.py --cluster nonprod --kubeconfig "$HOME/.kube/config-dev-stage"
# Run PROD only after NONPROD review:
python3 scripts/kubernetes/create-slack-secret.py --cluster prod --kubeconfig "$HOME/.kube/config-prod"
```

The helper verifies Prometheus's cluster external label, refuses non-interactive
prompts and existing Secrets, sends credentials to `kubectl create` through stdin,
and suppresses errors that could echo the request. It never writes credentials to
disk. The following names exist only after the approved command succeeds:

| Cluster | Secret in `monitoring` | Keys |
| --- | --- | --- |
| NONPROD | `monitoring-slack-nonprod` | `normal-webhook`, `testing-webhook` |
| PROD | `monitoring-slack-prod` | `normal-webhook`, `testing-webhook` |

The operator mounts those files at `/etc/alertmanager/secrets/<secret>/<key>`.
No Secret manifest or webhook URL is committed. Keep each cluster's credentials
and administrator access separate; limit Secret RBAC and use existing encryption
at rest and secure backup controls. Base64 encoding is not encryption. Do not
import the old kind Secret or reuse the PROD URL in NONPROD.

## Validation and approved rollout

Local validation uses Helm 3.20.0, amtool 0.34.1 and promtool 3.15.0. The latter
two match the live versions. Use the chart version/hash in
`kubernetes/platform/chart-lock.json` (92.2.0):

```sh
python3 scripts/kubernetes/validate-slack-alerting.py \
  --helm /path/to/helm --amtool /path/to/amtool --promtool /path/to/promtool \
  --chart /path/to/kube-prometheus-stack-92.2.0.tgz
```

The validator checks the chart checksum, YAML/schema, 72 route cases including
critical tests and wrong/missing cluster labels, per-alert FIRING/RESOLVED message
rendering, PromQL syntax/behavior, rendered Helm configuration equality and
Secret mounts. Rule fixtures cover node readiness, certificate units and threshold,
partial target failure, missing metrics and PROD replica failure. The full command
passed for both clusters. No credentials or cluster access are needed.

**Do not run rollout commands without explicit live-change approval.** Before
each cluster rollout, inspect again:

```sh
python3 scripts/kubernetes/inspect-slack-alerting.py --cluster nonprod
helm --kubeconfig "$HOME/.kube/config-dev-stage" -n monitoring history monitoring
kubectl --kubeconfig "$HOME/.kube/config-dev-stage" -n monitoring get secret monitoring-slack-nonprod -o name
```

Compare sanitized effective routing with Git. If someone has configured Slack
since this inspection, stop and reconcile that drift before upgrading. Preserve
the working receiver and credentials. Capture current Helm values and rule
manifests to an access-restricted recovery directory outside Git (`umask 077`),
record the revision and chart checksum, and review the rendered diff. Never dump
raw effective Alertmanager config or Secret contents into terminal logs.

After approval and credential preparation, use the existing Helm ownership path:

```sh
helm upgrade monitoring /path/to/kube-prometheus-stack-92.2.0.tgz \
  --kubeconfig "$HOME/.kube/config-dev-stage" --namespace monitoring \
  --values kubernetes/platform/nonprod/monitoring/values.yaml --wait --timeout 20m
kubectl --kubeconfig "$HOME/.kube/config-dev-stage" apply -f kubernetes/platform/nonprod/monitoring/rules.yaml
python3 scripts/kubernetes/inspect-slack-alerting.py --cluster nonprod --expect-slack
```

Confirm readiness and operator reconciliation, expected Secret mount names,
15 healthy loaded rules, cluster label, exact receivers, test precedence and
normal NONPROD channel before proceeding. The inspector prints only allowlisted
routing/receiver metadata and rule health; API status does not prove Slack delivery.
Inspect Prometheus `/api/v1/rules` privately to review loaded expressions/durations
and `/targets` for scrape failures.

Complete the NONPROD test below and review its actual Slack evidence. PROD rollout
requires separate approval after that review. Repeat the same commands using
`config-prod`, `prod` paths and `--cluster prod`; expect 16 healthy alerts and
`#liora-alerts-prod`. Do not run both rollouts as an unattended loop.

## Safe FIRING and RESOLVED test

Only after approved deployment and verification of webhook channel bindings:

```sh
kubectl --kubeconfig "$HOME/.kube/config-dev-stage" -n monitoring port-forward \
  --address=127.0.0.1 svc/monitoring-alertmanager 19093:9093
# In a second terminal in this checkout:
python3 scripts/kubernetes/test-slack-alert.py --cluster nonprod
```

The helper refuses legacy/mismatched routing before sending. It uses `purpose:
test`, the correct cluster and a unique test ID, confirms the testing receiver's
channel/file, and sets a 15-minute expiry. Confirm the first **FIRING message in
Slack** before pressing Enter to resolve that exact label set. Confirm the
**RESOLVED message in Slack** afterward; allow the 10-second group wait and
30-second update interval. It attempts resolution on interruption. If killed
abruptly or disconnected, the bounded expiry limits the alert lifetime.

Record both message links, test ID, cluster, time and expected channel. An HTTP
200 from Alertmanager, successful template rendering or notification counters
does **not** establish Slack receipt. Do not run the historical kind test helper
against these clusters: it lacks the required test/cluster labels.

After NONPROD review and explicit PROD test approval, stop the forward, forward
the PROD service with `config-prod`, and run `test-slack-alert.py --cluster prod`.
No test requires changing an application, adding persistent rules, stopping
nodes, deleting resources or disabling monitoring.

## Troubleshooting and recovery

- No notifications: check the cluster label, effective route, silences and
  inhibition, alert duration, group wait and the per-alert state. Use the inspector
  before assuming the Git config is active. Unknown cluster labels are discarded.
- Slack rejects delivery: verify the app is active and the channel still exists,
  the webhook's actual channel binding, outbound DNS/HTTPS and Secret key names.
  Inspect notification failure counters and logs privately; redact URLs before
  sharing any error. Do not try to fix binding by changing only `channel`.
- Missing RESOLVED: keep identical labels/test ID, ensure FIRING was actually
  observed first, wait for the update interval and check `send_resolved: true`.
- Rule missing/error: inspect PrometheusRule labels (`release: monitoring`),
  namespace, operator events and `/api/v1/rules` health. Check metric presence
  in the correct cluster. Missing data is not proof of recovery.
- Invalid reload: Alertmanager retains its last valid config; inspect reloader
  health and correct Git/Helm inputs. Never edit the generated Secret as a fix.
- Rollback: review `helm history` in the exact cluster, then use an approved
  `helm rollback monitoring <previous-revision>` with that cluster's kubeconfig.
  Separately restore the saved PrometheusRule manifest; Helm rollback does not
  own that extra resource. Keep the Slack Secrets for recovery. Do not uninstall
  monitoring, delete PVCs/Secrets/namespaces, or blindly restore a config that
  references missing credential files.
- Rotation: create replacement channel-bound URLs first, then securely update
  only that cluster's Secret through an approved stdin-based administrator
  process. Verify mounted files refresh, test receipt, and revoke old URLs only
  after the new credentials work. The create helper deliberately refuses overwrite.

## Exam evidence and remaining work

- [ ] Sanitized NONPROD and PROD architecture, VIPs and Helm ownership.
- [ ] Local validator output, tool versions and matching chart checksum.
- [ ] Both cluster rule inventories/health and normal/test receiver summaries.
- [ ] Slack app webhook list showing correct channel names, with all URLs hidden.
- [ ] Secret **names/key names only**, never data or base64 values.
- [ ] NONPROD FIRING and RESOLVED screenshots/message links with the same test ID.
- [ ] Separately approved PROD FIRING and RESOLVED evidence with PROD identity.
- [ ] Normal cluster routing evidence and alert template fields/severity/actions.
- [ ] Deployment approval, Helm revisions, rollback inputs and time of verification.

Initial Secret preparation, approved sequential deployment and both clusters'
FIRING/RESOLVED receipt checks are complete. Remaining manual work is to capture
exam screenshots/permanent Slack message links and maintain the app, webhook
rotation and access controls. Slack app administration and normal incident
webhook bindings were not directly inspected; normal routing was checked without
injecting alerts into incident channels. Testing-channel delivery was confirmed
by the user, including pasted messages, for both clusters.

Limitations: backup freshness/failure and public TLS expiry are not monitored by
these additions. A partially missing exporter metric family, a removed NONPROD
deployment or a node removed entirely from both discovery and inventory can still
escape per-resource detection. The missing-job list is tied to the inspected
architecture and must be reviewed when retiring a component. Prometheus or
Alertmanager being completely down cannot reliably alert through itself; an
independent external watchdog remains necessary for that failure mode.

References: [Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/),
[Slack incoming webhooks and channel binding](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/),
[K3s certificate metric implementation](https://github.com/k3s-io/k3s/blob/main/pkg/certmonitor/certmonitor.go),
[K3s certificate operations](https://docs.k3s.io/cli/certificate).
