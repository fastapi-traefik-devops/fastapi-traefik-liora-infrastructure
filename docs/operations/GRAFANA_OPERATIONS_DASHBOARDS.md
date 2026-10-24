# Operate Grafana dashboards

**Where:** Browser through Tailscale; management VM 200 for configuration.

## Dashboard reference

| Cluster | Endpoint | Operations UID |
| --- | --- | --- |
| NONPROD | `http://192.168.77.16:3000` | liora-nonprod-operations |
| PROD | `http://192.168.77.17:3000` | liora-prod-operations |

Each Grafana uses its cluster-local Prometheus datasource, UID `prometheus`.
Provisioned dashboards use native panels and JSON schema 39. Sources are the
cluster's `monitoring/dashboards.yaml` and `monitoring/operations-dashboard.yaml`.
Keep stable UIDs and the file-provisioning owner; do not create competing API/UI
copies of provisioned dashboards.

## 1. Investigate an incident

- [ ] Open the matching cluster and authenticate with protected Grafana credentials.
- [ ] In NONPROD select DEV, STAGE or All; keep cluster-wide panels distinct from namespace views.
- [ ] Start with request rate, errors and latency.
- [ ] Inspect application replicas, readiness and Argo health/sync.
- [ ] Inspect node/namespace capacity, requests/limits and active incidents.
- [ ] Follow detailed node, workload, ingress and GitOps dashboard links.
- [ ] Correlate alert identities with [Slack operations](SLACK_ALERTING.md), [database backup operations](../../runbooks/19-cnpg-r2-backup-pitr.md) and [storage/replication response](STORAGE_REPLICATION_ALERTS.md).

## Interpretation reference

| Display | Meaning / next check |
| --- | --- |
| Zero request rate | Observed idle counters; absent counters are missing telemetry. |
| Undefined latency/error fraction | No traffic or missing histogram/counter input; inspect the datasource before interpreting. |
| Database Pod Ready | Kubernetes readiness; inspect SQL/replication/backup metrics separately. |
| K3s certificate lifetime | Internal certificate lifetime; inspect cert-manager/served TLS for application certificates. |
| Healthy discovered targets | Discovered endpoints respond; also inspect expected missing jobs and metric-family alerts. |
| Local-path volume capacity | Shared backing filesystem, not a per-PVC directory quota. |

Traffic guides of 1%/5% errors and 300 ms/1 second p95 are display thresholds.
Prometheus rule definitions determine alert thresholds. One-minute dashboard
refresh and query min-step align with scrape/evaluation cadence.

## 2. Update dashboards

- [ ] Edit source/generator inputs, preserving datasource and dashboard UIDs.
- [ ] Generate and validate locally:

```sh
python3 scripts/kubernetes/build-operations-dashboards.py
python3 scripts/kubernetes/validate-operations-dashboards.py --promtool /path/to/promtool --kustomize /path/to/kustomize
```

Standalone scripts: [generator](../../scripts/kubernetes/build-operations-dashboards.py),
[validator](../../scripts/kubernetes/validate-operations-dashboards.py).

- [ ] Review the diff and save the selected cluster's existing dashboard ConfigMaps privately.
- [ ] Apply only that cluster's dashboard resources through the ownership path in [runbook 16](../../runbooks/16-private-platform-access.md).
- [ ] Wait for sidecar/file-provider reconciliation and check UIDs, titles, links, environment filters and panel queries.
- [ ] Validate live query behavior:

```sh
python3 scripts/kubernetes/validate-operations-dashboards.py --cluster nonprod --prometheus-url http://192.168.77.16:9090 --report .local-work/private/grafana-nonprod.json
```

- [ ] Repeat in PROD using `--cluster prod --prometheus-url http://192.168.77.17:9090` after NONPROD checks pass.

## 3. Recover configuration

- [ ] For a faulty revision, restore the selected source version and reapply only its dashboard ConfigMaps.
- [ ] Preserve monitoring PVCs, credentials, datasource and unrelated dashboard UIDs.
- [ ] Inspect the provider's `disableDelete` behavior when retiring a dashboard; remove only the exact retired UID after removing its source.
- [ ] Do not uninstall monitoring or roll back its entire Helm release for a dashboard-only correction.

**Done when:** Expected dashboards load with correct cluster/environment filters and no datasource or query errors.
