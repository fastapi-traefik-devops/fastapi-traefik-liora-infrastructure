# Operate monitoring and Slack notifications

**Where:** Management VM 200, infrastructure repository root.
**Order for changes:** NONPROD, then PROD.

## Configuration reference

| Cluster | Kubeconfig | Prometheus / Alertmanager | Incident channel |
| --- | --- | --- | --- |
| NONPROD | `$HOME/.kube/config-dev-stage` | `.16:9090` / `.16:9093`, HTTP | #liora-alerts-nonprod |
| PROD | `$HOME/.kube/config-prod` | `.17:9090` / `.17:9093`, HTTP | #liora-alerts-prod |

Helm owns `monitoring`; additional rules/monitors/dashboards use the cluster
monitoring Kustomizations. Do not edit generated Alertmanager Secrets or operator
workloads. Notification credentials remain private and independent per cluster.

## 1. Provision notification credentials

- [ ] Open **FastAPI DevOps → FastAPI Monitoring** in Slack application management.
- [ ] Confirm Incoming Webhooks and channel bindings for normal and synthetic destinations.
- [ ] Use separate normal/testing webhook entries for each cluster. Synthetic notifications belong only in `#liora-alerts-testing`.
- [ ] Keep webhook URLs in the protected recovery kit; never pass them in shell arguments or tracked files.
- [ ] Complete the initial chart submission in [runbook 16](../../runbooks/16-private-platform-access.md#2-install-monitoring) so the Prometheus resource and cluster identity exist.
- [ ] In an interactive private terminal, create the selected cluster's Secret:

```sh
python3 scripts/kubernetes/create-slack-secret.py --cluster nonprod --kubeconfig "$HOME/.kube/config-dev-stage"
```

Standalone script: [create-slack-secret.py](../../scripts/kubernetes/create-slack-secret.py).

- [ ] Repeat for PROD with `--cluster prod --kubeconfig "$HOME/.kube/config-prod"` after NONPROD checks.

| Cluster | Secret in `monitoring` | Keys |
| --- | --- | --- |
| NONPROD | monitoring-slack-nonprod | normal-webhook, testing-webhook |
| PROD | monitoring-slack-prod | normal-webhook, testing-webhook |

The helper uses hidden prompts and refuses existing Secrets. For rotation,
create replacement channel-bound URLs, update only the selected Secret using a
private stdin-based process, verify delivery, then revoke old URLs. A YAML
`channel` setting cannot retarget an incoming webhook's actual channel binding.

## 2. Validate and reconcile configuration

- [ ] Prepare the chart/version/hash from [chart-lock.json](../../kubernetes/platform/chart-lock.json) and the pinned local validation tools.
- [ ] Run local validation:

```sh
python3 scripts/kubernetes/validate-slack-alerting.py --helm /path/to/helm --amtool /path/to/amtool --promtool /path/to/promtool --chart .local-work/charts/kube-prometheus-stack-92.2.0.tgz
```

Standalone script: [validate-slack-alerting.py](../../scripts/kubernetes/validate-slack-alerting.py).

- [ ] Inspect effective routing and Helm history before changes:

```sh
python3 scripts/kubernetes/inspect-slack-alerting.py --cluster nonprod
helm --kubeconfig "$HOME/.kube/config-dev-stage" -n monitoring history monitoring
```

Standalone script: [inspect-slack-alerting.py](../../scripts/kubernetes/inspect-slack-alerting.py).

- [ ] Save current Helm values/revisions and separately managed rule manifests to protected storage. Review any drift before replacing configuration.
- [ ] Reconcile through [runbook 16](../../runbooks/16-private-platform-access.md#2-install-monitoring); then inspect:

```sh
python3 scripts/kubernetes/inspect-slack-alerting.py --cluster nonprod --expect-slack
bash scripts/local-python.sh scripts/kubernetes/audit-monitoring-alerts.py --cluster nonprod --output .local-work/private/nonprod-alerting-audit.json
```

Standalone script: [audit-monitoring-alerts.py](../../scripts/kubernetes/audit-monitoring-alerts.py).

- [ ] Require healthy loaded rules, correct cluster labels, expected receiver/Secret names and healthy scrape targets. Investigate nonzero audit results.
- [ ] Complete section 3 before repeating in PROD.

## 3. Check FIRING and RESOLVED delivery

- [ ] Confirm testing webhooks are bound to `#liora-alerts-testing`.
- [ ] Open a temporary loopback endpoint for the synthetic notification helper:

```sh
kubectl --kubeconfig "$HOME/.kube/config-dev-stage" -n monitoring port-forward --address=127.0.0.1 svc/monitoring-alertmanager 19093:9093
```

- [ ] In a second terminal, submit the bounded synthetic notification:

```sh
python3 scripts/kubernetes/test-slack-alert.py --cluster nonprod
```

Standalone script: [test-slack-alert.py](../../scripts/kubernetes/test-slack-alert.py).

- [ ] Confirm FIRING in Slack before resolving through the helper.
- [ ] Confirm RESOLVED with the same cluster and identifier. Record message links and UTC times without webhook URLs.
- [ ] Stop the temporary forward. Repeat with PROD's explicit kubeconfig and `--cluster prod`.

The helper requires loopback, verifies routing, uses `purpose="test"` and a unique
ID, and expires its alert after 15 minutes. No workload failure is required.
Permanent browser administration uses the Admin VIP; this temporary forward is
only the helper's constrained diagnostic path. Alertmanager API success alone
does not establish downstream delivery.

## Routing reference

- Exact cluster labels select the cluster-local route. Missing/wrong cluster labels are discarded.
- Synthetic `purpose="test"` routes precede incident routes and do not continue into them.
- Critical incidents: 30-second group wait, five-minute update, one-hour repeat.
- Warning incidents: one-minute group wait, five-minute update, 12-hour repeat.
- Both normal receivers send recovery notifications; no daily backup success messages.
- Messages include identity, severity, affected resource, UTC times, action and source/runbook links.
- Inhibition is dependency-specific. Keep independent database, WAL, overdue-backup and critical application conditions visible.

## Alert response checklist

| Alert family | Operator action |
| --- | --- |
| Node pressure/capacity/request saturation | Compare VM/guest memory with Kubernetes capacity and allocatable; inspect requests, limits and node events. |
| Application Pending/Failed/restarts/unavailable | Inspect actual Deployments/Pods/events, owner replacements and exporter health. |
| Argo unhealthy/out-of-sync | Inspect selected revision, sync operation, hooks and resource diff. |
| Target down/missing or missing metrics | Check discovery, endpoint, exporter and monitor labels; do not treat absent telemetry as recovery. |
| CNPG backup/coordinator/WAL | Use [runbook 19](../../runbooks/19-cnpg-r2-backup-pitr.md#4-recover-a-failed-or-interrupted-cycle); preserve locks and retained intent. |
| PVC space/inodes or standby/lag | Use [storage and replication response](STORAGE_REPLICATION_ALERTS.md). |
| Public certificate readiness/expiry | Inspect namespace `app-tls`, cert-manager events and served certificate using [runbook 15](../../runbooks/15-publish-application.md). |
| Internal K3s certificate expiry | Inspect `k3s_certificate_expiration_seconds`, which reports remaining lifetime rather than a Unix timestamp. |
| Notification failures | Inspect Prometheus→Alertmanager and Alertmanager→Slack health, outbound HTTPS, routing and webhook bindings. |

- [ ] Open the alert's source link and inspect the metric labels for the affected cluster/environment.
- [ ] Check silences/inhibition and current condition before declaring an outage or recovery.
- [ ] On invalid reload, correct Git/Helm input; preserve the last valid runtime configuration.
- [ ] For rollback, select the correct Helm revision and restore separately managed rule manifests separately. Preserve Secrets/PVCs.
- [ ] Never delete application data, stop live nodes or fail a database solely to exercise notification delivery.

Prometheus/Alertmanager outages require independent external observation;
self-monitoring cannot cover loss of its own entire notification path. Public
uptime/certificate monitoring complements internal alerts.

**Done when:** Effective routing matches the intended cluster, rules/targets are healthy, and both synthetic notification states arrive in their expected channel.
