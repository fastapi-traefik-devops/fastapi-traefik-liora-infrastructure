# Alerting runbook

Scope: existing `kind-fastapi-dev` monitoring with DEV and STAGE application alerts. Node alerts cover the shared local node. Rules are in [monitoring/rules/dev-stage.yaml](monitoring/rules/dev-stage.yaml); thresholds and durations were preserved. All eight have severity `warning`.

## Alert lifecycle and notification limits

Prometheus evaluates the expressions every 60s. True enters pending; remaining true for the rule's `for` duration enters firing. A false result clears pending/firing on the next evaluation. Missing series also stop an alert; missing telemetry is **not** evidence of recovery. The duration is additional to the rate/increase lookback, not a requirement to wait the entire lookback after a fault starts. Allow scrape/evaluation alignment delay.

Alertmanager is discovered by Prometheus and its API is operational, but the configured receiver is `null`: **there are no email, Slack or paging notifications**. Alerts are visible in Prometheus `/alerts` and Alertmanager UI. Routing groups by `alertname,namespace`, waits 1m initially, groups subsequent changes every 5m and repeats after 12h. Node alerts without a namespace group together by alertname. `resolve_timeout=5m` is a fallback for clients without an end time; it does not replace the rule `for` duration. Single instance has no HA peer cluster.

No notification destination or credentials were supplied, so no external delivery was configured or tested. To enable delivery later, provide the receiver/destination, store credentials in a Secret, update `monitoring/values.yaml` and the active monitoring source, then test delivery and resolution with a clearly named test alert. That is a separate authorized messaging change. Do not treat API health or a null receiver as successful paging.

These eight rules do not alert on exporter disappearance, missing applications, TLS expiry, backups or application-specific request errors. The Platform Overview `up` panel requires attention when telemetry fails. FastAPI currently has no native request metrics. Default kube-prometheus rules are disabled. Additional coverage should be a deliberate follow-up rather than assumed to exist.

## Alerts

### NodeMemoryPressure

```promql
kube_node_status_condition{condition="MemoryPressure",status="true"} == 1
```

Measures / why it matters: Kubernetes reports MemoryPressure=true; indicates eviction risk, not simply a percentage of used RAM.

Healthy: MemoryPressure true-condition gauge is 0.

Fires / unhealthy: Gauge equals 1 continuously for 5m. Rule `for: 5m`.

Action: Inspect node conditions/events and host/node RAM. Find expensive pods with top; reduce competing load, investigate leaks/OOMs. Avoid launching CI into pressure.

### NodeDiskPressure

```promql
kube_node_status_condition{condition="DiskPressure",status="true"} == 1
```

Measures / why it matters: Kubernetes reports DiskPressure=true; indicates low disk space or inodes and possible evictions.

Healthy: DiskPressure true-condition gauge is 0.

Fires / unhealthy: Gauge equals 1 continuously for 5m. Rule `for: 5m`.

Action: Check node events, df -h and df -i; inspect image, log and PVC growth. Review safe cleanup or storage expansion; do not delete application data/PVCs.

### NodeHighCPU

```promql
(1 - avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))) > 0.85
```

Measures / why it matters: Five-minute non-idle CPU fraction averaged over cores for each exporter instance; catches sustained compute saturation.

Healthy: At or below 85%, with spare capacity.

Fires / unhealthy: Strictly above 85% continuously for 15m, after rate samples are available. Short spikes do not fire. Rule `for: 15m`.

Action: Check kubectl top pods -A and docker stats; correlate load with Traefik latency. Reduce concurrency, fix busy loops or provide capacity. Instance is an exporter address, not a Kubernetes node name.

### NodeHighMemory

```promql
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.90
```

Measures / why it matters: Unavailable memory fraction using MemAvailable/MemTotal; identifies loss of memory headroom before pressure.

Healthy: At or below 90%.

Fires / unhealthy: Strictly above 90% continuously for 15m. Rule `for: 15m`.

Action: Check free -h, top pods, limits and previous termination reasons. Reduce load and inspect leaks. Exporter reflects kernel/host view in kind, not a guaranteed Docker budget.

### ApplicationRestartSpike

```promql
sum by(namespace,pod,container) (increase(kube_pod_container_status_restarts_total{namespace=~"app-dev|app-stage"}[15m])) >= 3
```

Measures / why it matters: Counter increase for each DEV/STAGE pod/container over 15m; catches repeated crashes.

Healthy: No recent restarts; fewer than 3 in the rolling window.

Fires / unhealthy: At least 3 estimated restarts within 15m and the expression remains true for 5m. Per container, not pooled across all pods. Rule `for: 5m`.

Action: Describe affected pod; inspect last termination/OOMKilled and logs --previous. Review probes, secrets, DB connectivity and image changes. New pod identity resets history; counter extrapolation may be fractional.

### ApplicationDeploymentUnavailable

```promql
kube_deployment_status_replicas_available{namespace=~"app-dev|app-stage"} < kube_deployment_spec_replicas{namespace=~"app-dev|app-stage"}
```

Measures / why it matters: Available replicas below desired for a DEV/STAGE Deployment; catches sustained loss of serving capacity.

Healthy: Available equals desired; intentional desired=0 does not fire.

Fires / unhealthy: Available < desired continuously for 10m. Rule `for: 10m`.

Action: Inspect rollout status and deployment/pod events. Check Pending, pull errors, missing secrets, failed prestart migration and readiness. Diagnose before restarting or rolling back.

### ArgoApplicationUnhealthy

```promql
argocd_app_info{name=~"app-dev|app-stage",health_status!="Healthy"} == 1
```

Measures / why it matters: Argo app-dev/app-stage health is anything other than Healthy; captures Degraded, Progressing, Missing, Unknown and other nonhealthy states.

Healthy: Both expected Applications report Healthy.

Fires / unhealthy: argocd_app_info=1 with health_status != Healthy continuously for 10m. Synced can still be unhealthy. Rule `for: 10m`.

Action: Inspect Argo conditions/resource tree and operation state; identify unhealthy Deployment/Job and inspect events/logs. Long planned Progressing or Suspended states can trigger this broad rule.

### ArgoApplicationOutOfSync

```promql
argocd_app_info{name=~"app-dev|app-stage",sync_status!="Synced"} == 1
```

Measures / why it matters: Argo app-dev/app-stage sync state is anything other than Synced; catches drift or comparison problems.

Healthy: Both Applications report Synced.

Fires / unhealthy: argocd_app_info=1 with sync_status != Synced continuously for 10m. Unknown also matches. Healthy can still be out of sync. Rule `for: 10m`.

Action: Review Git diff, manifest-generation errors and last operation. Resolve intended DEV/STAGE desired state and reconcile; do not blindly sync unknown changes or point unpublished monitoring paths at Git.

## Safe investigation commands

Replace `app-dev` with `app-stage` when indicated by the alert. Replace POD/DEPLOYMENT/NODE with the actual names; do not substitute exporter IPs for node names.

```bash
kubectl --context kind-fastapi-dev top nodes
kubectl --context kind-fastapi-dev top pods -A
kubectl --context kind-fastapi-dev describe node NODE
kubectl --context kind-fastapi-dev get events -n app-dev --sort-by=.lastTimestamp
kubectl --context kind-fastapi-dev describe pod POD -n app-dev
kubectl --context kind-fastapi-dev logs POD -n app-dev -c backend --previous --tail=100
kubectl --context kind-fastapi-dev rollout status deployment/DEPLOYMENT -n app-dev --timeout=30s
kubectl --context kind-fastapi-dev get application app-dev -n argocd -o yaml
```

For Argo errors inspect controller and repo-server logs in `argocd`. Keep secret values out of shared diagnostic outputs. Clear root causes and verify metrics, application health and traffic before considering an alert resolved. A silence suppresses notifications and does not fix a fault; scope any planned silence narrowly and give it an expiry/reason.

## Inspect and validate alert plumbing

In separate terminals:

```bash
kubectl --context kind-fastapi-dev port-forward --address=127.0.0.1 -n monitoring svc/monitoring-prometheus 19090:9090
kubectl --context kind-fastapi-dev port-forward --address=127.0.0.1 -n monitoring svc/monitoring-alertmanager 19093:9093
```

Prometheus: http://127.0.0.1:19090/targets and /alerts. Alertmanager: http://127.0.0.1:19093. Inspect `/api/v1/rules`, `/api/v1/alertmanagers`, `/api/v2/status`, `/api/v2/alerts`. Useful plumbing queries:

```promql
prometheus_notifications_alertmanagers_discovered
increase(prometheus_notifications_errors_total[15m])
```

The first counts discovered receivers (healthy=1 here; unhealthy=0); restore Service/endpoints/discovery if absent. The second counts failed Prometheus sends (healthy=0; unhealthy=increasing); inspect notification logs and Alertmanager connectivity. Neither establishes external delivery with a null receiver. Full panel/target validation: `python3 infra/kind/scripts/verify-kind-monitoring.py` (close existing forwards first).

Synthetic validation: with the Prometheus forward active, `python3 monitoring/test-alert-rules.py`. It compares the locally documented rules with loaded canonical expressions, durations, labels and annotations, then uses promtool with fabricated samples to assert no premature firing, firing at the expected evaluation, recovery, healthy thresholds and application environment isolation. It does not stress the node, alter app replicas, inject alerts into Alertmanager or send messages. `.tools/promtool` was copied from the existing running Prometheus image (version 3.15.0); on another machine provide a matching promtool binary at that ignored path. Tests run in temporary local storage because the Prometheus container filesystem is read-only. The synthetic PROD labels in tests are fabricated data only; no PROD resources are read or changed.

## FastAPI instrumentation assessment — proposal only

No Prometheus dependency/import or route is present in `backend/pyproject.toml` or `backend/app/main.py`; native `/metrics` currently returns 404. Existing pod metrics and Traefik metrics work without application changes, but cannot expose route-template app duration or app-specific business metrics.

A bounded, opt-in middleware is reasonable for DEV/STAGE's current one-worker execution, subject to dependency resolution, tests and overhead measurement. Compatibility is plausible from the declared Starlette/Python constraints; it is not a tested lockfile resolution. The Dockerfile default is **four workers**. A plain process-local registry with four workers would report whichever worker handled each scrape. Keep one worker for this proposal; do not enable it in multiworker environments without a tested multiprocess registry/directory lifecycle. No backend, dependency, lockfile, image, ServiceMonitor or ingress change has been implemented.

Exact proposed dependency addition to `backend/pyproject.toml`:

```toml
"prometheus-fastapi-instrumentator==7.1.0",
```

This pin requires Python >=3.8, Starlette >=0.30,<1 and prometheus-client >=0.8,<1 per the [tagged dependency declaration](https://github.com/trallnag/prometheus-fastapi-instrumentator/blob/v7.1.0/pyproject.toml). Resolve with `uv lock` in `backend`, inspect and retain `backend/uv.lock` changes, then `uv sync --frozen`. No dependency installation was performed here.

Exact proposed imports in `backend/app/main.py`:

```python
import os
from prometheus_fastapi_instrumentator import Instrumentator
```

Append **after** the existing `app.include_router(...)`:

```python
if os.getenv("ENABLE_METRICS", "false").lower() == "true":
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=[r"^/metrics$", r"^/api/v1/utils/health-check/$"],
    ).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
```

Set `ENABLE_METRICS=true` only in the DEV/STAGE backend environment patches, retaining `--workers 1`. Default false leaves other environments unchanged. Use route templates, grouped response codes and no user IDs/raw paths/custom payload labels; unmatched routes and health/scrape traffic are excluded. No body collectors are added. `include_in_schema=False` also avoids this project's `route.tags[0]` OpenAPI-ID callback on the untagged metrics route. The [tagged instrumentator implementation](https://github.com/trallnag/prometheus-fastapi-instrumentator/blob/v7.1.0/src/prometheus_fastapi_instrumentator/instrumentation.py) supports these options. For multiworker operation, review the [official Python client multiprocess requirements](https://prometheus.github.io/client_python/multiprocess/) before enabling metrics.

Proposed scraping: avoid altering the shared base Service or public ingress. Add a **new internal-only backend-metrics Service in each DEV/STAGE overlay**, with metadata labels `app: backend-metrics`, selector `app: backend`, port `name: metrics`, `port: 8000`, `targetPort: 8000`. Then add this ServiceMonitor under `monitoring` and include it in the active inline source as well as local Kustomize/bootstrap definitions:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: fastapi-dev-stage
  namespace: monitoring
  labels:
    release: monitoring
spec:
  namespaceSelector:
    matchNames: [app-dev, app-stage]
  selector:
    matchLabels:
      app: backend-metrics
  endpoints:
  - port: metrics
    path: /metrics
    interval: 60s
    scrapeTimeout: 10s
```

Existing app ingress uses `/` on the API host, so exposing `/metrics` on port 8000 would also make it routable there. **Before enabling**, add a DEV/STAGE-specific Traefik restriction for the exact `/metrics` path (including `/metrics/` redirect variant), using an IP allowlist middleware/route that denies external access while direct internal metrics Service scraping remains allowed; or implement a dedicated private metrics listener. Confirm external requests are rejected and internal scraping succeeds. Simply omitting an explicit metrics ingress is insufficient with the existing catch-all route. Do not modify the PROD/shared ingress.

Validate in DEV first: disabled flag preserves `/metrics` 404, enabled route returns Prometheus content, OpenAPI generation remains valid, auth/CORS/errors/streaming behavior and existing backend tests pass, request counters/histograms advance after known traffic, route cardinality remains bounded, each replica has an UP target, and CPU/memory/latency overhead fits capacity. Rebuild and deploy the immutable DEV image, then STAGE after validation. Tests should use isolated registries/app construction to avoid duplicate collector registration. Rollback: disable the DEV/STAGE flag or restore prior image and remove/disable its proposed ServiceMonitor; leave existing infrastructure monitoring intact.

## Validation record

Validated on 2026-10-09 19:02:03 UTC, context `kind-fastapi-dev`:

- **16/16 active scrape targets UP**, no scrape errors; required exporters present.
- All 29 dashboard expressions returned live series; Workloads was checked for both namespaces. Some idle latency series correctly remained NaN; benign DEV/STAGE requests produced finite HTTP entrypoint and all four DEV/STAGE service p95 measurements.
- Four updated dashboards provisioned under the original UIDs. Stored panel definitions match local source. **37 panel/namespace query checks** returned real data through Grafana: Platform 8, Workloads 16, Argo 6, Traefik 7.
- Eight requested rules loaded, `health=ok`, no evaluation errors, and inactive during validation. Synthetic promtool tests passed for all eight pending/firing/recovery scenarios plus healthy thresholds and application scope isolation.
- Alertmanager `/api/v2/status` and `/api/v2/alerts` returned 200; 0 active alerts, one discovered endpoint, Prometheus notification error counters 0. Receiver remains `null`; external notification delivery was neither configured nor tested.
- Argo monitoring/app-dev/app-stage all Synced/Healthy, operations Succeeded. All six monitoring pods Ready with zero restarts. Dashboard-only change caused the expected Grafana rollout; other monitoring Application spec values were compared before/after and preserved.
- No stack reinstall, PROD changes, backend/dependency implementation, commit or push. Temporary verifier forwards were closed. No browser visual review or sustained-load performance claim.

Detailed diagnostic output: `.tools/verify-monitoring-operational.log` (ignored local artifact). Repeat commands are above and in [GRAFANA_DASHBOARDS.md](GRAFANA_DASHBOARDS.md). The three documents are the operational reference; earlier setup reports describe prior snapshots.
