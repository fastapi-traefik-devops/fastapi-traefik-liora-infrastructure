# Dashboard incident summaries

These dashboards remain Git-provisioned through `monitoring/dashboards/platform.yaml`.
All four UIDs, the Environment selector, and every existing panel/query are
preserved. Only existing panel vertical positions move to fit the new summaries.
No application, scrape, alert-rule, Slack, authentication, or storage settings change.

## Live metric and label inventory (2026-10-17 UTC)

- Argo: `argocd_app_info` exposes `name`, `health_status`, `sync_status`, and
  `dest_namespace`. Both `app-dev` and `app-stage` returned Healthy/Synced.
- Workloads: kube-state-metrics exposes desired/available replicas, restart
  counters, and `kube_pod_container_resource_requests` / `_limits`, with
  `namespace`, `pod`, `container`, `resource` and `unit` labels. CPU units are
  `core`; memory units are `byte`. cAdvisor exposes CPU counters and memory
  working sets with the same namespace/pod/container identity. Each new budget
  query returned four container series per environment. No app-prod series exist.
- Traefik: request counters expose `entrypoint` (`web`, `websecure`), `code`
  (`200`, `404` observed), and service counters expose `service` names such as
  `app-dev-backend-80@kubernetes` and `app-stage-frontend-80@kubernetes`.
  Histograms expose `le` plus entrypoint/service labels. No host/router labels
  exist on these metrics; service names already separate DEV/STAGE in the
  preserved request and p95 panels.
- Prometheus: the self-scrape uses `job="monitoring-prometheus"`; the rule-group
  gauge reports eight loaded rules. `ALERTS` is a rule-generated series present
  only while a rule is pending/firing; its live result was empty, consistent with
  the Rules API reporting no firing rules. The new alert count returned zero,
  guarded by the observed UP self-scrape. It counts Prometheus rule alerts, not
  synthetic alerts posted directly to Alertmanager.

## Additions and exact queries

Queries below were run directly against live Prometheus before adding panels.
All 18 query/environment variants returned finite data. `$namespace` is the
existing selector, checked separately for `app-dev` and `app-stage`.

### Argo applications Healthy (`platform-nodes`)

```promql
sum(argocd_app_info{name=~"app-dev|app-stage",health_status="Healthy"}) or (0 * sum(argocd_app_info{name=~"app-dev|app-stage"}))
```

Live check: platform: 1 series.

### Argo applications Synced (`platform-nodes`)

```promql
sum(argocd_app_info{name=~"app-dev|app-stage",sync_status="Synced"}) or (0 * sum(argocd_app_info{name=~"app-dev|app-stage"}))
```

Live check: platform: 1 series.

### Missing replicas (`platform-nodes`)

```promql
sum(clamp_min(kube_deployment_spec_replicas{namespace=~"app-dev|app-stage"} - kube_deployment_status_replicas_available{namespace=~"app-dev|app-stage"}, 0))
```

Live check: platform: 1 series.

### Container restarts (15m) (`platform-nodes`)

```promql
sum(increase(kube_pod_container_status_restarts_total{namespace=~"app-dev|app-stage"}[15m]))
```

Live check: platform: 1 series.

### Firing alerts (`platform-nodes`)

```promql
sum(ALERTS{alertstate="firing"}) or (0 * max(up{job="monitoring-prometheus"} == 1))
```

Live check: platform: 1 series.

### CPU usage / requests (`dev-stage-workloads`)

```promql
sum by(namespace,pod,container) (rate(container_cpu_usage_seconds_total{namespace="$namespace",container!="",container!="POD"}[5m])) / on(namespace,pod,container) (max by(namespace,pod,container) (kube_pod_container_resource_requests{namespace="$namespace",resource="cpu",unit="core"}) > 0)
```

Live check: app-dev: 4 series, app-stage: 4 series.

### CPU usage / limits (`dev-stage-workloads`)

```promql
sum by(namespace,pod,container) (rate(container_cpu_usage_seconds_total{namespace="$namespace",container!="",container!="POD"}[5m])) / on(namespace,pod,container) (max by(namespace,pod,container) (kube_pod_container_resource_limits{namespace="$namespace",resource="cpu",unit="core"}) > 0)
```

Live check: app-dev: 4 series, app-stage: 4 series.

### MEMORY usage / requests (`dev-stage-workloads`)

```promql
sum by(namespace,pod,container) (container_memory_working_set_bytes{namespace="$namespace",container!="",container!="POD"}) / on(namespace,pod,container) (max by(namespace,pod,container) (kube_pod_container_resource_requests{namespace="$namespace",resource="memory",unit="byte"}) > 0)
```

Live check: app-dev: 4 series, app-stage: 4 series.

### MEMORY usage / limits (`dev-stage-workloads`)

```promql
sum by(namespace,pod,container) (container_memory_working_set_bytes{namespace="$namespace",container!="",container!="POD"}) / on(namespace,pod,container) (max by(namespace,pod,container) (kube_pod_container_resource_limits{namespace="$namespace",resource="memory",unit="byte"}) > 0)
```

Live check: app-dev: 4 series, app-stage: 4 series.

### DEV / STAGE application status (`gitops-argocd`)

```promql
max by(name,health_status,sync_status) (argocd_app_info{name=~"app-dev|app-stage"})
```

Live check: platform: 2 series.

### Total request rate (`ingress-traefik`)

```promql
sum(rate(traefik_entrypoint_requests_total[5m]))
```

Live check: platform: 1 series.

### HTTP 2xx rate (`ingress-traefik`)

```promql
sum(rate(traefik_entrypoint_requests_total{code=~"2.."}[5m])) or (0 * sum(rate(traefik_entrypoint_requests_total[5m])))
```

Live check: platform: 1 series.

### HTTP 4xx rate (`ingress-traefik`)

```promql
sum(rate(traefik_entrypoint_requests_total{code=~"4.."}[5m])) or (0 * sum(rate(traefik_entrypoint_requests_total[5m])))
```

Live check: platform: 1 series.

### HTTP 5xx rate (`ingress-traefik`)

```promql
sum(rate(traefik_entrypoint_requests_total{code=~"5.."}[5m])) or (0 * sum(rate(traefik_entrypoint_requests_total[5m])))
```

Live check: platform: 1 series.

## Interpretation and preserved panels

The overview expects two Healthy and two Synced Argo applications: red below
one, yellow at one, green at two. Missing Argo telemetry stays no data, not green.
Positive missing replicas/restarts/firing alerts get warning/error colors. These
are display thresholds, not alert-rule changes.

Budget charts show usage divided by the observed positive request/limit for
that container, matching namespace/pod/container. Empty/POD sandbox containers
are excluded. Missing or zero budgets have no series: no fabricated limit is
shown. 80% is yellow and 100% red as visual investigation cues. Requests are
scheduling reservations, so above 100% of requests can be normal bursting.

The Argo table is an instant query with explicit Application/Health/Sync columns.
Healthy/Synced are green; Degraded/OutOfSync are red. Missing applications have
no table row; use the expected-count Stats to detect them. Existing state,
health, sync, sync-operation-rate, reconciliation-p95, and Git-rate panels stay.

HTTP rate Stats aggregate existing entrypoints; absent matching status counters
produce zero only when base request counters exist. No request telemetry is no
data. No 5xx samples were induced. Existing 4xx/5xx fraction trends, service
requests, entrypoint/service p95 and reload panels remain. Histogram p95 may be
NaN when idle; this is absence of observations, not zero latency.

Restart history already exists as `Container restarts in 15m`:

```promql
increase(kube_pod_container_status_restarts_total{namespace="$namespace"}[15m])
```

Both existing p95 queries remain:

```promql
histogram_quantile(0.95,sum by(le,entrypoint) (rate(traefik_entrypoint_request_duration_seconds_bucket[5m])))
histogram_quantile(0.95,sum by(le,service) (rate(traefik_service_request_duration_seconds_bucket{service=~"app-(dev|stage)-.*"}[5m])))
```

## Validation and rollout

JSON parsing, unique panel IDs and preservation of all original panels/queries
were checked. Existing monitoring and authentication verifiers passed on the
current deployed baseline: 16 UP targets, eight healthy rules, four dashboards,
normal login and anonymous API rejection. The monitoring verifier makes benign
GET requests to existing DEV/STAGE routes; it does not change workloads.

Every new query was tested live. All 55 old/new panel/environment queries passed directly in Prometheus and
through authenticated Grafana datasource queries before publication. All
returned finite samples, including p95 under the verifier’s benign traffic.
The Argo result exposed name/health_status/sync_status as frame labels; the
table uses labelsToFields followed by organize to display those columns. This is
query validation, not a claim that unmerged panels are already provisioned.
After merging to main, let Argo reconcile the ConfigMap, then run:

```sh
python3 infra/kind/scripts/verify-kind-monitoring.py
python3 monitoring/verify-grafana-auth.py
```

The verifiers honor a panel target's table format and compare Git definitions
with provisioned Grafana panels. GitOps reconciliation and visual browser review
must be reported separately from query checks. No PROD panels are added because
app-prod workload metrics are absent; no host/router filtering is invented.
