# Independent local runtime evidence index

Run: 24 October 2026, Europe/Tirane. **25 captures, 24 unique genuine images**.

Product UI views are actual local browsers; command views are labeled renderings of saved real output. Synthetic data used in real software is distinguished from the separate historical simulation images. No new simulated screenshots were created.

[Audit](../DR_INDEPENDENT_AUDIT_REPORT.md) · [Runtime report](../LOCAL_DISASTER_RECOVERY_TEST_REPORT.md) · [Presentation](../DR_PRESENTATION_FINAL_EVIDENCE.md) · [Historical references](HISTORICAL_REFERENCES.md)

## 01-kubernetes

- [01-api-node.jpg](screenshots/kubernetes/01-api-node.jpg)
- [02-storage-rollout.jpg](screenshots/kubernetes/01-api-node.jpg)
- [03-pvc-marker-proof.jpg](screenshots/kubernetes/03-pvc-marker-proof.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/01-kubernetes/RESULT.md)
- [create-retry.log](../evidence/real/2026-10-24-local/01-kubernetes/create-retry.log)
- [create.log](../evidence/real/2026-10-24-local/01-kubernetes/create.log)
- [preflight-observations.json](../evidence/real/2026-10-24-local/01-kubernetes/preflight-observations.json)
- [storage-proof.log](../evidence/real/2026-10-24-local/01-kubernetes/storage-proof.log)
- [verification-retry.log](../evidence/real/2026-10-24-local/01-kubernetes/verification-retry.log)
- [verification.log](../evidence/real/2026-10-24-local/01-kubernetes/verification.log)

## 02-cloudnativepg-r2

- [01-operator-install.jpg](screenshots/cloudnativepg-r2/01-operator-install.jpg)
- [02-plugin-certificates.jpg](screenshots/cloudnativepg-r2/02-plugin-certificates.jpg)
- [03-ready-certificates-proof.jpg](screenshots/cloudnativepg-r2/03-ready-certificates-proof.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/02-cloudnativepg-r2/RESULT.md)
- [dependencies.log](../evidence/real/2026-10-24-local/02-cloudnativepg-r2/dependencies.log)
- [input-preflight.json](../evidence/real/2026-10-24-local/02-cloudnativepg-r2/input-preflight.json)
- [operator-install.log](../evidence/real/2026-10-24-local/02-cloudnativepg-r2/operator-install.log)
- [ready-proof.log](../evidence/real/2026-10-24-local/02-cloudnativepg-r2/ready-proof.log)

## 03-application

- [01-image-pull-failure.jpg](screenshots/application/01-image-pull-failure.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/03-application/RESULT.md)
- [database-bootstrap.log](../evidence/real/2026-10-24-local/03-application/database-bootstrap.log)
- [database-ready.log](../evidence/real/2026-10-24-local/03-application/database-ready.log)
- [events.log](../evidence/real/2026-10-24-local/03-application/events.log)
- [startup.log](../evidence/real/2026-10-24-local/03-application/startup.log)

## 04-argocd

- [01-applications-ui.jpg](screenshots/argocd/01-applications-ui.jpg)
- [02-synced-applications-ui.jpg](screenshots/argocd/02-synced-applications-ui.jpg)
- [03-sync-tree-ui.jpg](screenshots/argocd/03-sync-tree-ui.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/04-argocd/RESULT.md)
- [free-resources.log](../evidence/real/2026-10-24-local/04-argocd/free-resources.log)
- [install.log](../evidence/real/2026-10-24-local/04-argocd/install.log)
- [sync-retry.log](../evidence/real/2026-10-24-local/04-argocd/sync-retry.log)
- [sync.log](../evidence/real/2026-10-24-local/04-argocd/sync.log)

## 05-monitoring

- [01-prometheus-target-up.jpg](screenshots/monitoring/01-prometheus-target-up.jpg)
- [02-prometheus-rules.jpg](screenshots/monitoring/02-prometheus-rules.jpg)
- [03-grafana-real-local-metrics.jpg](screenshots/monitoring/03-grafana-real-local-metrics.jpg)
- [04-recovered-repository-dashboard.jpg](screenshots/monitoring/04-recovered-repository-dashboard.jpg)
- [05-alertmanager-synthetic-firing.jpg](screenshots/monitoring/05-alertmanager-synthetic-firing.jpg)
- [06-alertmanager-resolved.jpg](screenshots/monitoring/06-alertmanager-resolved.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/05-monitoring/RESULT.md)
- [alertmanager-address.txt](../evidence/real/2026-10-24-local/05-monitoring/alertmanager-address.txt)
- [alertmanager-firing.json](../evidence/real/2026-10-24-local/05-monitoring/alertmanager-firing.json)
- [alertmanager-resolved.json](../evidence/real/2026-10-24-local/05-monitoring/alertmanager-resolved.json)
- [alertmanager-status.json](../evidence/real/2026-10-24-local/05-monitoring/alertmanager-status.json)
- [alertmanager.log](../evidence/real/2026-10-24-local/05-monitoring/alertmanager.log)
- [grafana-dashboards.json](../evidence/real/2026-10-24-local/05-monitoring/grafana-dashboards.json)
- [grafana-health.json](../evidence/real/2026-10-24-local/05-monitoring/grafana-health.json)
- [grafana.log](../evidence/real/2026-10-24-local/05-monitoring/grafana.log)
- [prometheus.log](../evidence/real/2026-10-24-local/05-monitoring/prometheus.log)
- [query.json](../evidence/real/2026-10-24-local/05-monitoring/query.json)
- [ready.log](../evidence/real/2026-10-24-local/05-monitoring/ready.log)
- [resource-usage.log](../evidence/real/2026-10-24-local/05-monitoring/resource-usage.log)
- [rule-validation.log](../evidence/real/2026-10-24-local/05-monitoring/rule-validation.log)
- [rules.json](../evidence/real/2026-10-24-local/05-monitoring/rules.json)
- [targets.json](../evidence/real/2026-10-24-local/05-monitoring/targets.json)

## 06-jenkins

- [01-source-controller-held.jpg](screenshots/jenkins/01-source-controller-held.jpg)
- [02-restored-controller-held.jpg](screenshots/jenkins/02-restored-controller-held.jpg)
- [03-restored-disabled-job.jpg](screenshots/jenkins/03-restored-disabled-job.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/06-jenkins/RESULT.md)
- [archive-receipt.json](../evidence/real/2026-10-24-local/06-jenkins/archive-receipt.json)
- [image-pull.log](../evidence/real/2026-10-24-local/06-jenkins/image-pull.log)
- [resource-usage.log](../evidence/real/2026-10-24-local/06-jenkins/resource-usage.log)
- [restored-runtime.json](../evidence/real/2026-10-24-local/06-jenkins/restored-runtime.json)
- [restored-startup.log](../evidence/real/2026-10-24-local/06-jenkins/restored-startup.log)
- [source-runtime.json](../evidence/real/2026-10-24-local/06-jenkins/source-runtime.json)
- [source-startup.log](../evidence/real/2026-10-24-local/06-jenkins/source-startup.log)
- [staging.log](../evidence/real/2026-10-24-local/06-jenkins/staging.log)

## 07-rollback

- [01-workload-v1-v2-v1.jpg](screenshots/rollback/01-workload-v1-v2-v1.jpg)
- [02-postgres-checkpoint-restore.jpg](screenshots/rollback/02-postgres-checkpoint-restore.jpg)
- [03-http-comparison.jpg](screenshots/rollback/03-http-comparison.jpg)
- [04-sql-comparison.jpg](screenshots/rollback/04-sql-comparison.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/07-rollback/RESULT.md)
- [cluster-resume.log](../evidence/real/2026-10-24-local/07-rollback/cluster-resume.log)
- [first-failure.log](../evidence/real/2026-10-24-local/07-rollback/first-failure.log)
- [first-run.log](../evidence/real/2026-10-24-local/07-rollback/first-run.log)
- [http-comparison.log](../evidence/real/2026-10-24-local/07-rollback/http-comparison.log)
- [postgres-proof.log](../evidence/real/2026-10-24-local/07-rollback/postgres-proof.log)
- [results.json](../evidence/real/2026-10-24-local/07-rollback/results.json)
- [rollback.log](../evidence/real/2026-10-24-local/07-rollback/rollback.log)
- [sql-comparison.log](../evidence/real/2026-10-24-local/07-rollback/sql-comparison.log)
- [workload-proof.log](../evidence/real/2026-10-24-local/07-rollback/workload-proof.log)

## 08-cleanup

- [01-pvc-before-shutdown.jpg](screenshots/cleanup/01-pvc-before-shutdown.jpg)
- [02-stopped-and-preserved.jpg](screenshots/cleanup/02-stopped-and-preserved.jpg)
- [RESULT.md](../evidence/real/2026-10-24-local/08-cleanup/RESULT.md)
- [after-shutdown.log](../evidence/real/2026-10-24-local/08-cleanup/after-shutdown.log)
- [before-shutdown.log](../evidence/real/2026-10-24-local/08-cleanup/before-shutdown.log)
- [cleanup.log](../evidence/real/2026-10-24-local/08-cleanup/cleanup.log)
- [receipt.json](../evidence/real/2026-10-24-local/08-cleanup/receipt.json)
