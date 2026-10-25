# Prometheus queries and operational interpretation

Scope: existing `kind-fastapi-dev` cluster, DEV (`app-dev`) and STAGE (`app-stage`). No PROD changes. Scrape/evaluation interval: 60s; rates use 5m, restart increases use 15m. Retention: 3d or 1500MB, whichever is reached first. Run these in Prometheus Expression browser or Grafana Explore, datasource `Prometheus` (UID `prometheus`).

Replace `$namespace` with `app-dev` or `app-stage` in plain Prometheus. Grafana Workloads provides that selector. To compare both environments, replace `namespace="$namespace"` with `namespace=~"app-dev|app-stage"` and use `sum by(namespace)` for namespace totals. For cluster-wide pod CPU/memory, remove the namespace filter from the pod queries. One CPU core is 1000 millicores. Fractions range 0–1; Grafana formats them as percentages.

No samples is not healthy. Check `up`, discovery and scrape errors first. Restart `increase` is extrapolated and can be fractional; a new pod starts a new counter. No traffic produces zero rates and undefined (NaN) histogram quantiles. Error ratios below use observed request series as the zero baseline and preserve absent telemetry; the tiny denominator guard makes idle observed series 0, not evidence of successful traffic. Never average per-service quantiles to derive global p95.

## Local kind metric boundaries

This is one kind node on a shared Docker host. Node-exporter CPU/memory reflect the Linux kernel/host view, not a Docker cgroup capacity guarantee. Cluster aggregate equals the one exporter view today. Use cAdvisor pod metrics, `kubectl top`, host `free -h`, and `docker stats --no-stream` together for capacity decisions. Filesystem series include repeated bind mounts of the same host device; do not sum them. Pressure conditions are Kubernetes node signals, not the same as exporter percentage thresholds. Shared platform/entrypoint/Git metrics cover this cluster; application-specific queries select DEV/STAGE.

## Query catalog

### Node CPU busy fraction

```promql
1 - avg by(instance) (rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m]))
```

Measures / why it matters: Fraction of CPU time outside idle; identifies sustained saturation.

Healthy: Below 85%, with headroom for builds.

Unhealthy: Above 85% for 15m triggers NodeHighCPU.

Action: Check kubectl top pods -A; reduce competing jobs or add capacity.

### Node memory used fraction

```promql
1 - node_memory_MemAvailable_bytes{job="node-exporter"} / node_memory_MemTotal_bytes{job="node-exporter"}
```

Measures / why it matters: Memory unavailable for new allocations, allowing for reclaimable cache; tracks OOM risk.

Healthy: Below 90%, with available headroom.

Unhealthy: Above 90% for 15m triggers NodeHighMemory.

Action: Check host free -h and kubectl top pods -A; reduce load and inspect leaks.

### Cluster CPU busy fraction

```promql
1 - sum(rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m])) / count(node_cpu_seconds_total{job="node-exporter",mode="idle"})
```

Measures / why it matters: CPU-weighted cluster busy fraction; indicates aggregate capacity.

Healthy: Below 85% and no saturated individual node.

Unhealthy: Sustained high usage or a hot node hidden by the average.

Action: Use the per-node panel to locate saturation; investigate heavy pods.

### Cluster memory used fraction

```promql
1 - sum(node_memory_MemAvailable_bytes{job="node-exporter"}) / sum(node_memory_MemTotal_bytes{job="node-exporter"})
```

Measures / why it matters: Capacity-weighted unavailable memory fraction; indicates aggregate headroom.

Healthy: Below 90% and no pressured node.

Unhealthy: High aggregate use or individual-node pressure.

Action: Compare per-node usage with workload memory and host available RAM.

### Filesystem available bytes

```promql
node_filesystem_avail_bytes{job="node-exporter",fstype!~"tmpfs|overlay|squashfs"}
```

Measures / why it matters: Bytes available to ordinary users per filesystem; detects storage exhaustion.

Healthy: Stable free capacity sufficient for retention and image growth.

Unhealthy: Falling capacity or DiskPressure.

Action: Check df -h and df -i on host/node; review image/log growth and PVC usage before cleanup.

### Node conditions

```promql
kube_node_status_condition{status="true",condition=~"Ready|MemoryPressure|DiskPressure|PIDPressure"}
```

Measures / why it matters: Kubernetes node condition gauges; eviction and readiness signals.

Healthy: Ready=1; all pressure conditions=0.

Unhealthy: Ready=0 or any pressure condition=1.

Action: Describe the node and inspect events, RAM, disk and inodes.

### Scrape target availability

```promql
up
```

Measures / why it matters: 1 for successful scrape, 0 for failed scrape; detects missing monitoring data.

Healthy: All expected targets=1.

Unhealthy: A target=0, missing expected target, or stale samples.

Action: Open Prometheus /targets; inspect lastError, selector labels, endpoints and exporter pod logs.

### Alertmanager instances discovered

```promql
prometheus_notifications_alertmanagers_discovered
```

Measures / why it matters: Number of discovered Alertmanager endpoints; verifies routing discovery.

Healthy: 1 in this single-instance setup.

Unhealthy: 0 or unexpected loss of discovery.

Action: Inspect Prometheus /api/v1/alertmanagers and monitoring-alertmanager endpoints.

### Pod CPU

```promql
sum by(namespace,pod) (rate(container_cpu_usage_seconds_total{namespace="$namespace",container!="",container!="POD"}[5m]))
```

Measures / why it matters: CPU seconds per second across real containers; 1 core=1000m, identifies expensive pods.

Healthy: Stable use with headroom against limits.

Unhealthy: Sustained limit-level use, throttling or growing latency.

Action: Inspect top pods, resource requests/limits and request volume.

### Pod memory

```promql
sum by(namespace,pod) (container_memory_working_set_bytes{namespace="$namespace",container!="",container!="POD"})
```

Measures / why it matters: Container working set summed by pod; indicates memory demand, not exact RSS.

Healthy: Stable below container limits with node headroom.

Unhealthy: Steady growth, limit proximity, OOMKilled or pressure.

Action: Inspect each container, previous logs and memory limits; investigate leaks.

### Namespace CPU

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="$namespace",container!="",container!="POD"}[5m]))
```

Measures / why it matters: Total DEV or STAGE workload CPU cores; supports environment capacity comparison.

Healthy: Stable relative to workload and node capacity.

Unhealthy: Unexpected growth or competition with other namespaces.

Action: Compare DEV/STAGE pod CPU and recent deployments/load.

### Namespace memory

```promql
sum(container_memory_working_set_bytes{namespace="$namespace",container!="",container!="POD"})
```

Measures / why it matters: Total environment working set; shows memory footprint.

Healthy: Stable with adequate node capacity.

Unhealthy: Rising footprint or loss of headroom.

Action: Identify the growing pod and inspect its memory limits and logs.

### Available deployment replicas

```promql
kube_deployment_status_replicas_available{namespace="$namespace"}
```

Measures / why it matters: Available replicas; shows whether workloads can serve traffic.

Healthy: Equals desired replicas (currently one per deployment).

Unhealthy: Below desired replicas.

Action: Describe deployment/pods and inspect rollout, probes and image/secret errors.

### Missing deployment replicas

```promql
clamp_min(kube_deployment_spec_replicas{namespace="$namespace"} - kube_deployment_status_replicas_available{namespace="$namespace"}, 0)
```

Measures / why it matters: Desired minus available replicas; highlights service capacity deficits.

Healthy: 0 for every deployment, including intentional scale-to-zero.

Unhealthy: Positive for 10m triggers ApplicationDeploymentUnavailable.

Action: Inspect rollout status, scheduling events and readiness probes.

### Container restarts in 15m

```promql
increase(kube_pod_container_status_restarts_total{namespace="$namespace"}[15m])
```

Measures / why it matters: Recent restart count estimated from a counter; catches crashes rather than historical totals.

Healthy: 0; occasional explained rollout events.

Unhealthy: At least 3 per container in 15m, sustained for 5m.

Action: Describe pod; inspect last termination reason and logs --previous; fix crash/OOM/probe causes.

### Pod readiness

```promql
kube_pod_status_ready{namespace="$namespace",condition="true"}
```

Measures / why it matters: 1 when pod is Ready; detects pods unable to serve.

Healthy: 1 for long-running serving pods.

Unhealthy: 0 for a serving pod; completed prestart Jobs may legitimately be 0.

Action: Check pod phase and owner first, then readiness probe and events.

### Application state

```promql
argocd_app_info{name=~"app-dev|app-stage"}
```

Measures / why it matters: Argo application labels expose health and sync independently; value is always 1.

Healthy: Labels Healthy and Synced for both apps.

Unhealthy: Degraded/Progressing/Missing/Unknown or OutOfSync/Unknown sustained.

Action: Inspect Argo application conditions, resource tree, operation and Git diff.

### Application healthy

```promql
argocd_app_info{name=~"app-dev|app-stage",health_status="Healthy"} or on(name) (0 * argocd_app_info{name=~"app-dev|app-stage"})
```

Measures / why it matters: Boolean health indicator preserving zero for observed unhealthy apps.

Healthy: 1 for each expected app.

Unhealthy: 0 means unhealthy; no series means missing telemetry or deleted app.

Action: Inspect resource health and application conditions; check exporter if absent.

### Application synced

```promql
argocd_app_info{name=~"app-dev|app-stage",sync_status="Synced"} or on(name) (0 * argocd_app_info{name=~"app-dev|app-stage"})
```

Measures / why it matters: Boolean sync indicator; detects divergence from desired state.

Healthy: 1 for each expected app.

Unhealthy: 0 means not Synced; no series is not healthy.

Action: Review Argo diff and manifest-generation errors; reconcile only intended DEV/STAGE changes.

### Sync operation rate

```promql
sum by(name,phase) (rate(argocd_app_sync_total{name=~"app-dev|app-stage"}[5m]))
```

Measures / why it matters: Sync operations per second by result; spots repeated failures/reconciliation loops.

Healthy: Zero when idle; occasional successful sync.

Unhealthy: Repeated failed sync or unexpected loops.

Action: Inspect last operation, hooks, Git source and permissions.

### Reconciliation p95

```promql
histogram_quantile(0.95,sum by(le,dest_server) (rate(argocd_app_reconcile_bucket[5m])))
```

Measures / why it matters: Estimated 95th percentile Argo comparison/reconciliation time across the shared controller; this exporter has no application-name label on this histogram.

Healthy: Stable near baseline; idle windows can be NaN.

Unhealthy: Persistent increase relative to baseline.

Action: Inspect controller/repo-server logs, Git connectivity and API latency.

### Git request rate

```promql
sum by(request_type) (rate(argocd_git_request_total[5m]))
```

Measures / why it matters: Shared repo-server Git requests; helps diagnose GitOps activity.

Healthy: Low steady polling and spikes during expected operations.

Unhealthy: Repeated retries or unexplained sustained spikes.

Action: Inspect repo-server errors and repository availability; correlate with sync failures.

### Entrypoint requests

```promql
sum by(entrypoint,code) (rate(traefik_entrypoint_requests_total[5m]))
```

Measures / why it matters: Ingress requests per second by HTTP code, including unmatched routing.

Healthy: Expected request volume and mostly successful responses.

Unhealthy: Unexpected drop, spikes, or rising 4xx/5xx.

Action: Check endpoint reachability, ingress rules and service readiness.

### DEV / STAGE service requests

```promql
sum by(service,code) (rate(traefik_service_requests_total{service=~"app-(dev|stage)-.*"}[5m]))
```

Measures / why it matters: Service request rate; attributes traffic to DEV/STAGE backend/frontend.

Healthy: Expected traffic with mostly 2xx.

Unhealthy: Rising service errors or sudden traffic disappearance.

Action: Use service name to select namespace; check endpoints and backend logs.

### Entrypoint 4xx fraction

```promql
(sum by(entrypoint) (rate(traefik_entrypoint_requests_total{code=~"4.."}[5m])) or on(entrypoint) (0 * sum by(entrypoint) (rate(traefik_entrypoint_requests_total[5m])))) / clamp_min(sum by(entrypoint) (rate(traefik_entrypoint_requests_total[5m])), 1e-9)
```

Measures / why it matters: Fraction of requests rejected as client errors; helps detect routing/auth issues.

Healthy: Near baseline, normally near 0 for test traffic.

Unhealthy: Unexpected sustained increase; expected 401/404 may be legitimate.

Action: Inspect response codes, routes and auth; correlate with deployment changes.

### Entrypoint 5xx fraction

```promql
(sum by(entrypoint) (rate(traefik_entrypoint_requests_total{code=~"5.."}[5m])) or on(entrypoint) (0 * sum by(entrypoint) (rate(traefik_entrypoint_requests_total[5m])))) / clamp_min(sum by(entrypoint) (rate(traefik_entrypoint_requests_total[5m])), 1e-9)
```

Measures / why it matters: Fraction of ingress requests failing server-side; reveals upstream outages.

Healthy: 0 for successful test traffic.

Unhealthy: Any sustained unexpected 5xx.

Action: Check backend readiness/endpoints/logs and Traefik timeout/connect errors.

### Entrypoint latency p95

```promql
histogram_quantile(0.95,sum by(le,entrypoint) (rate(traefik_entrypoint_request_duration_seconds_bucket[5m])))
```

Measures / why it matters: Estimated p95 ingress duration from histogram; detects user-facing slowness.

Healthy: Stable relative to baseline under comparable traffic.

Unhealthy: Persistent increase; NaN during idle is no observation.

Action: Check request rate, service latency, backend CPU and database behavior.

### DEV / STAGE service latency p95

```promql
histogram_quantile(0.95,sum by(le,service) (rate(traefik_service_request_duration_seconds_bucket{service=~"app-(dev|stage)-.*"}[5m])))
```

Measures / why it matters: Estimated upstream-service p95 duration; helps localize ingress latency.

Healthy: Stable baseline under comparable requests.

Unhealthy: Increasing service p95; NaN when idle.

Action: Identify service/environment and inspect app/database performance.

### Last reload successful

```promql
traefik_config_last_reload_success
```

Measures / why it matters: 1 when last dynamic configuration reload succeeded; detects invalid ingress configuration.

Healthy: 1.

Unhealthy: 0 or missing series.

Action: Inspect Traefik logs and recently changed ingress/service configuration.

## Validated target inventory

2026-10-09 UTC: all 16 active targets UP, no scrape lastError. Each target was checked through `/api/v1/targets`; panels were queried against the live samples.

| Scrape pool / endpoint index | Job | Health |
| --- | --- | --- |
| `podMonitor/monitoring/traefik/0` | `monitoring/traefik` | UP |
| `serviceMonitor/monitoring/argocd-metrics/0` | `argocd-metrics` | UP |
| `serviceMonitor/monitoring/argocd-repo-server/0` | `argocd-repo-server` | UP |
| `serviceMonitor/monitoring/argocd-server-metrics/0` | `argocd-server-metrics` | UP |
| `serviceMonitor/monitoring/monitoring-alertmanager/0` | `monitoring-alertmanager` | UP |
| `serviceMonitor/monitoring/monitoring-alertmanager/1` | `monitoring-alertmanager` | UP |
| `serviceMonitor/monitoring/monitoring-apiserver/0` | `apiserver` | UP |
| `serviceMonitor/monitoring/monitoring-grafana/0` | `monitoring-grafana` | UP |
| `serviceMonitor/monitoring/monitoring-kube-state-metrics/0` | `kube-state-metrics` | UP |
| `serviceMonitor/monitoring/monitoring-kubelet/0` | `kubelet` | UP |
| `serviceMonitor/monitoring/monitoring-kubelet/1` | `kubelet` | UP |
| `serviceMonitor/monitoring/monitoring-kubelet/2` | `kubelet` | UP |
| `serviceMonitor/monitoring/monitoring-operator/0` | `monitoring-operator` | UP |
| `serviceMonitor/monitoring/monitoring-prometheus-node-exporter/0` | `node-exporter` | UP |
| `serviceMonitor/monitoring/monitoring-prometheus/0` | `monitoring-prometheus` | UP |
| `serviceMonitor/monitoring/monitoring-prometheus/1` | `monitoring-prometheus` | UP |

The three kubelet endpoints supply normal kubelet metrics, cAdvisor and probes. Endpoint index 1 for Prometheus/Alertmanager monitors the config reloader. Discovery showed 280 dropped candidates at the initial inspection; relabel/selector exclusions are not failed active targets. Disabled controller-manager, scheduler, etcd, kube-proxy and CoreDNS monitors are intentionally absent. FastAPI and Jenkins are not instrumented/scraped; an absent target is not evidence of health. Existing target configuration was preserved.

The final [verification record](ALERTING_RUNBOOK.md#validation-record) distinguishes target health, rule evaluation, synthetic firing tests, dashboard data and notification limits.
