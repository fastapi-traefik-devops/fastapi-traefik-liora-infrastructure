# Slack alerting deployment — 2026-10-23

The user explicitly approved deployment and synthetic testing of both clusters.
NONPROD was deployed and its FIRING/RESOLVED Slack messages confirmed before PROD
deployment. Only alerts labeled `purpose: test` were injected; their effective
receiver was `slack-testing`.

| Check | NONPROD | PROD |
| --- | --- | --- |
| Helm release / chart | monitoring / kube-prometheus-stack 92.2.0 | monitoring / kube-prometheus-stack 92.2.0 |
| Previous → deployed revision | 2 → 3 | 1 → 2 |
| Loaded platform alerts | 15, all health=ok | 16, all health=ok |
| Monitoring pods | 8, all containers ready | 8, all containers ready |
| Monitoring PVCs | 2 Bound | 2 Bound |
| Normal receiver / configured channel | slack-nonprod / #liora-alerts-nonprod | slack-prod / #liora-alerts-prod |
| Synthetic receiver / channel | slack-testing / #liora-alerts-testing | slack-testing / #liora-alerts-testing |
| FIRING receipt in Slack | Confirmed by user, message pasted in chat | Confirmed by user, message pasted in chat |
| RESOLVED receipt in Slack | Confirmed by user | Confirmed by user, message pasted in chat |

## Evidence

- NONPROD test ID: `a65a86f3-8b1b-4af3-8fcc-2afc217db6f8`.
  Started at **13:19:54 UTC** (15:19:54 Europe/Tirane).
- PROD test ID: `1517791d-a23f-4583-bffa-0e3c8f477a34`.
  Started at **13:23:26 UTC** (15:23:26 Europe/Tirane).
  Resolved at **13:24:11 UTC** (15:24:11 Europe/Tirane).
- Both pasted FIRING messages included the correct cluster, `TEST` environment,
  `info` severity, namespace, description, suggested action, test ID and start
  time. The same alert labels were retained when submitting resolution.
- Slack failure counters were checked without exposing URLs. Alertmanager API
  acceptance and notification counters are supporting evidence; user-observed
  Slack messages establish actual receipt.
- Final Slack notification counters were **2 per cluster**, with **zero Slack
  notification failures**. Neither test ID remained active after resolution.
- Both live Helm user-values configurations matched the reviewed per-cluster
  files. The read-only inspector confirmed the expected effective routing,
  receiver templates, cluster identity and healthy alert inventories.
- The original eight alert expressions, durations and severities were retained.
  No application, node, namespace, PVC or Secret was deleted to exercise alerts.

## Validation and recovery inputs

Local validation passed with Helm 3.20.0, amtool 0.34.1 and promtool 3.15.0:
72 routing combinations, template rendering, rule syntax and behavioral fixtures,
chart checksum, rendered configuration equality and Secret mounts. The chart
SHA256 matched `kubernetes/platform/chart-lock.json`.

Private rollback inputs are on the management server, outside Git, under:

- NONPROD: `/home/root-admin/.local/state/liora-monitoring/20261023T131715Z/nonprod`
- PROD: `/home/root-admin/.local/state/liora-monitoring/20261023T132127Z/prod`

These access-restricted directories contain previous Helm values/history,
PrometheusRule manifests, effective Alertmanager configuration, render output
and deployment logs. Review them privately; do not attach raw configuration or
logs to public reports. Existing Slack Secret data and UIDs were checked before
and after each deployment and remained unchanged.

Follow [the runbook](../../../operations/SLACK_ALERTING.md) for approved rollback. Helm rollback must
be paired with separately restoring the saved rule manifest, because Helm does
not own that PrometheusRule.

## Helper compatibility and shared checkout

Alertmanager 0.34.1 automatically includes receiver-name metadata in its status
configuration. The synthetic helper originally rejected this field. Commit
`76455ad` accepts only the expected receiver name and adds regression checks for
raw, normalized and invalid metadata; no routing relaxation was introduced.
The fix was committed and pushed to infrastructure `main` as `dionis1`.

The server checkout contained concurrent, unrelated local commits and edits.
They were not merged, reset, rebased, staged or committed by this deployment.
The two unchanged helper files were updated in place to exactly match `76455ad`;
these appear as local modifications until the shared branch is reconciled by its
owner. Monitoring deployment inputs were unchanged from the reviewed commit.
Temporary test processes/forwards exited, and the temporary runner was removed.

## Scope and remaining limitations

Normal incident-channel delivery was not deliberately triggered; its routing and
credential separation were verified. Both synthetic tests used only the testing
receiver. Channel bindings are controlled by the Slack webhooks; changing YAML
`channel` alone cannot retarget them.

Backup freshness/failure alerts, public edge TLS expiry and an independent
external monitoring watchdog remain separate work. No backup alert was added by
this deployment. Exam screenshots and permanent Slack message links can be
collected using the test IDs above; webhook URLs must remain hidden.
