# Cluster monitoring adaptation

Adapted from the history-preserved `../../upstream/monitoring/` inputs. Use
kube-prometheus-stack 92.2.0 and the archive hash in `../../chart-lock.json`.
Helm owns the chart release; this kustomization owns only additional resources.
No platform Argo Application competes for the same resources.

The values retain bounded PoC resource budgets, three-day/1500MB Prometheus
retention with a 2Gi PVC, a 256Mi Alertmanager PVC and provisioned, ephemeral
Grafana UI state. Both PVCs use node-local `local-path`. Every cluster uses its
own login Secret, datasource display name, dashboards, platform alert rules and native
IP-and-port URLs. The datasource UID is preserved for imported panels. Argo CD
Services retain their actual selectors; the Traefik PodMonitor targets
`kube-system` with instance `traefik-kube-system`. Exporter/operator endpoints
remain internal. Cluster-specific Slack routing and additional metric-backed rules
are prepared in Git; deployment requires separately provisioned credentials and
explicit approval. The old kind Slack Secret is not imported. Follow the
[Slack alerting runbook](../../../../docs/operations/SLACK_ALERTING.md) for
current routing, validation, rollout gates and verification status.

Apply the [approved status ownership guard](../../../../docs/testreports/decisions/admin-vip-status-ownership.md) before
creating VIP Services, then chart values with Helm and this directory with
kubectl. Actual sequential rollout and acceptance are in the Phase 8 report.

Grafana source limits were insufficient: the first 384Mi instance was OOMKilled
during native browser verification. Both clusters now request 100m/256Mi and
limit 500m/768Mi, with a 15-minute startup probe allowance for cold migrations.
Other component budgets retain the bounded source settings.
