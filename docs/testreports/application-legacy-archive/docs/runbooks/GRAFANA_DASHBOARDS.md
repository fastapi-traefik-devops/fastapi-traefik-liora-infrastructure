# Grafana dashboards

Four existing dashboards improved in place, retaining their UIDs/bookmarks. Datasource: `Prometheus`, UID `prometheus`, server-side proxy to `http://monitoring-prometheus.monitoring.svc.cluster.local:9090`. Refresh 1m; default range last hour. Scrapes/evaluations are 60s, so these are operational trends rather than instantaneous measurements.

| Dashboard | UID / URL path | Panels and purpose |
| --- | --- | --- |
| Platform Overview | `platform-nodes` / `/d/platform-nodes` | Cluster and per-node CPU/memory, filesystem free bytes, Ready/pressure conditions, scrape availability, Alertmanager discovery. Start here for capacity or telemetry problems. |
| DEV / STAGE Workloads | `dev-stage-workloads` / `/d/dev-stage-workloads` | Namespace CPU/memory, pod CPU/memory, available and missing deployment replicas, recent container restarts, pod readiness. Environment selector permits only `app-dev` or `app-stage`; verify both before attributing shared-node pressure. |
| Argo CD | `gitops-argocd` / `/d/gitops-argocd` | Application state with health/sync labels, explicit health and sync indicators, sync rate by phase, shared reconciliation p95, shared Git request rate. Use to distinguish drift from unhealthy runtime resources. |
| Traefik | `ingress-traefik` / `/d/ingress-traefik` | Entrypoint requests by code, DEV/STAGE service requests, 4xx and 5xx fractions, entrypoint and DEV/STAGE service p95, configuration reload success. Use service names to attribute traffic to environments. |

All panels include descriptions of the measurement, healthy/unhealthy interpretation and next action. Metric-specific guidance and the exact expressions are in [PROMETHEUS_QUERIES.md](PROMETHEUS_QUERIES.md). CPU/memory fraction panels use percentage units and 85%/90% thresholds. CPU cores, bytes, requests/second and latency seconds have explicit units. Legends name the actual node/pod/container/deployment/application/service/code; Argo state labels are visible rather than a misleading constant `1` with no health information.

No observations is distinct from zero. Latency quantiles are undefined during idle periods; the panels leave gaps rather than inventing zero latency. Restart increases may be fractional due to Prometheus extrapolation. Completed Jobs may have readiness 0 without an application outage. Argo health/sync indicators return 0 for an observed unhealthy/out-of-sync app but disappear if app telemetry disappears. EntryPoint traffic and Git/reconciliation panels describe shared components. The live reconciliation histogram lacks application-name labels, so it cannot honestly be split by DEV/STAGE.

## Access

```bash
kubectl --context kind-fastapi-dev port-forward --address=127.0.0.1 -n monitoring svc/monitoring-grafana 13000:80
```

Open http://127.0.0.1:13000/login and use the existing admin account backed by `monitoring-grafana-admin` Secret. Anonymous access is disabled. Credentials are not stored in these documents. Dashboards appear in the existing `DEV-STAGE` folder. No public ingress is introduced.

## Provisioning and changes

Source definitions: [monitoring/dashboards/platform.yaml](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/blob/2a6e05a91489b2d9475e25157ab73d8ff9c98d08/monitoring/dashboards/platform.yaml). The ConfigMap carries the existing `grafana_dashboard: '1'` label. [monitoring/bootstrap.py](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/blob/2a6e05a91489b2d9475e25157ab73d8ff9c98d08/monitoring/bootstrap.py) embeds the same definitions in Helm values for the currently active unpublished-source bootstrap.

The live monitoring Application currently uses chart source plus inline values, not the unpublished Git paths. This change patched **only** `spec.source.helm.valuesObject.grafana.dashboards.default` on that Application, preserving chart version, authentication, datasource, storage, resources, monitors, alert rules and sync policy. Argo reconciles the existing resources; no Helm installation or stack reinstall. Do not blindly apply `argocd/app-monitoring.yaml` before its Git paths are published. No publication, commit or push was performed.

Grafana dashboards are provisioned and UI editing is disabled. Grafana storage is ephemeral, so source definitions are the durable copy. Future edits should update the local dashboard file and the existing active source consistently; preserve UIDs. The bootstrap helper also emits paused installation settings, so applying its whole output to the running Application is not a dashboard-update procedure.

## Repeatable validation

```bash
python3 infra/kind/scripts/verify-kind-monitoring.py
```

The verifier opens temporary loopback forwards, checks every active target and required exporter, generates three rounds of benign GETs to each DEV/STAGE frontend and health endpoint, waits for real finite Traefik latency, checks the eight rules and Alertmanager API/discovery, authenticates to Grafana, compares provisioned panel definitions to source, and queries every panel through both Prometheus and Grafana. Both namespace selections are checked. It closes its own forwards. Close any forwards already occupying ports 19090/19093/13000 before running it.

Validation evidence and limitations are recorded at the end of [ALERTING_RUNBOOK.md](ALERTING_RUNBOOK.md). API/provisioning/query checks establish real data; they do not claim a browser visual review or a sustained load test.
