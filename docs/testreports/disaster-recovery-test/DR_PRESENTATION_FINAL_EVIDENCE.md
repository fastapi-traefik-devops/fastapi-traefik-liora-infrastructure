# Liora — Disaster recovery presentation evidence

25 captured genuine screenshots (24 unique images) collected; selected strongest views below. Product UIs are direct browser captures of running local components. Command-output views are explicitly labeled viewers of real saved logs, not terminal-window screenshots.

Keep three scopes separate in every slide: new local runtime tests; synthetic local data/workloads; historical original-environment PITR documentation. Never describe the logical table rollback as an R2 PITR restore or the local lab as full Proxmox DR.

## Local storage survives pod replacement

- Screenshot: [03-pvc-marker-proof.jpg](astra-review/screenshots/kubernetes/03-pvc-marker-proof.jpg)
- Demonstrates: Actual Bound PVC, new pod and unchanged marker.
- Say: “I replaced the pod and read the same marker from its persistent volume.”
- Limitation: One node and local-path storage; not disk-loss recovery.

## Recovery dependencies boot independently

- Screenshot: [03-ready-certificates-proof.jpg](astra-review/screenshots/cloudnativepg-r2/03-ready-certificates-proof.jpg)
- Demonstrates: Real CNPG/Barman startup and ready TLS certificates.
- Say: “The documented backup operators can start in an isolated local Kubernetes lab.”
- Limitation: No physical R2 backup or WAL was restored.

## Recovery exposes missing inputs

- Screenshot: [01-image-pull-failure.jpg](astra-review/screenshots/application/01-image-pull-failure.jpg)
- Demonstrates: Actual HTTP 401 for the pinned app images.
- Say: “The local attempt exposed registry authentication as a missing recovery prerequisite.”
- Limitation: This is failure evidence, not successful application recovery.

## GitOps recovery with a safe local destination

- Screenshot: [03-sync-tree-ui.jpg](astra-review/screenshots/argocd/03-sync-tree-ui.jpg)
- Demonstrates: Actual Argo Synced/Healthy status and successful revision.
- Say: “Argo reconciled a sanitized application ConfigMap from a separate local Git repository.”
- Limitation: Only one ConfigMap; full DEV/STAGE applications remained held.

## Prometheus recovers and scrapes

- Screenshot: [01-prometheus-target-up.jpg](astra-review/screenshots/monitoring/01-prometheus-target-up.jpg)
- Demonstrates: Actual self-scrape target UP.
- Say: “The restored monitoring runtime collected real samples locally.”
- Limitation: No production exporters or historical TSDB were recovered.

## Existing alert rules load successfully

- Screenshot: [02-prometheus-rules.jpg](astra-review/screenshots/monitoring/02-prometheus-rules.jpg)
- Demonstrates: Actual repository rule groups evaluated with healthy rule state.
- Say: “Thirty existing rule definitions passed syntax checking and loaded in Prometheus.”
- Limitation: Healthy rule evaluation does not establish all target metrics exist.

## A real monitoring dashboard after recovery

- Screenshot: [03-grafana-real-local-metrics.jpg](astra-review/screenshots/monitoring/03-grafana-real-local-metrics.jpg)
- Demonstrates: Live up=1 and process-memory series from the local Prometheus.
- Say: “These are live measurements from the local runtime, not invented dashboard values.”
- Limitation: This extra runtime dashboard was created for the lab.

## Dashboard configuration survives independently

- Screenshot: [04-recovered-repository-dashboard.jpg](astra-review/screenshots/monitoring/04-recovered-repository-dashboard.jpg)
- Demonstrates: Original Liora operations dashboard imported locally.
- Say: “The dashboard JSON restored correctly; absent exporters are shown honestly as no telemetry.”
- Limitation: Visual configuration recovered; original telemetry/history did not.

## Alert processing without external notifications

- Screenshot: [05-alertmanager-synthetic-firing.jpg](astra-review/screenshots/monitoring/05-alertmanager-synthetic-firing.jpg)
- Demonstrates: Actual synthetic alert under the discard receiver.
- Say: “I tested alert acceptance in an isolated network without sending Slack messages.”
- Limitation: Synthetic alert input; no production delivery test.

## Alert resolution is verified

- Screenshot: [06-alertmanager-resolved.jpg](astra-review/screenshots/monitoring/06-alertmanager-resolved.jpg)
- Demonstrates: Actual no-alert-groups state after resolution.
- Say: “The same test alert resolved, and the API confirmed zero active alerts.”
- Limitation: Only the local synthetic alert lifecycle was tested.

## Jenkins starts safely from a staged archive

- Screenshot: [02-restored-controller-held.jpg](astra-review/screenshots/jenkins/02-restored-controller-held.jpg)
- Demonstrates: Actual restored controller with quiet banner and no executors.
- Say: “The existing repository helper produced a home that a second Jenkins controller could start.”
- Limitation: Synthetic local controller data and core Jenkins; not original plugins/history.

## Recovered automation stays disabled

- Screenshot: [03-restored-disabled-job.jpg](astra-review/screenshots/jenkins/03-restored-disabled-job.jpg)
- Demonstrates: Actual restored disabled freestyle job.
- Say: “The restored job remained disabled; no builds or deployment automation ran.”
- Limitation: Empty build history; original pipeline recovery is not demonstrated.

## A real Kubernetes rollback

- Screenshot: [03-http-comparison.jpg](astra-review/screenshots/rollback/03-http-comparison.jpg)
- Demonstrates: Recorded actual HTTP v1 → v2 → v1 and preserved PVC marker.
- Say: “A real rollout undo recovered the earlier service response in about 2.2 seconds.”
- Limitation: BusyBox HTTP fixture, not the Liora application; screenshot is a labeled log viewer.

## PostgreSQL checkpoint recovery

- Screenshot: [04-sql-comparison.jpg](astra-review/screenshots/rollback/04-sql-comparison.jpg)
- Demonstrates: Actual SQL before/change/restore and pg_restore command.
- Say: “The checkpoint removed the later row and restored the original marker in about 0.6 seconds.”
- Limitation: Logical synthetic-table restore; not R2, WAL replay or PITR. Log-viewer screenshot.

## Safe cleanup preserves existing workloads

- Screenshot: [02-stopped-and-preserved.jpg](astra-review/screenshots/cleanup/02-stopped-and-preserved.jpg)
- Demonstrates: Actual empty docker ps, retained original containers, original context and clean repos.
- Say: “All test workloads stopped, and the original containers and their volumes remained available.”
- Limitation: Stopped lab storage/images remain on disk. Screenshot is a labeled log viewer.

## Existing repository evidence, kept historical

- [Phase 10.2 report](../phases/phase-10/history/r2-backup-pitr-2026-10-23.md): suggested slide “Previously documented DEV/STAGE/PROD PITR”. Say: “The repository reports three PITR exercises on 23 October; those were separate from today’s local tests.” Mention that the historical timing excludes rebuilding K3s/Proxmox, and physical backup availability was not reverified today. This is a document, not an original PITR execution screenshot.

- [Historical NONPROD assurance screenshot](../evidence/grafana-operations/nonprod-assurance.png): suggested slide “Historical operational observability”. It shows original environment delivery/database readiness. Say: “This is an existing repository monitoring screenshot.” Its older backup panel explicitly says NOT INSTRUMENTED; do not present it as successful backup/restore evidence.

- [Historical PROD operations screenshot](../evidence/grafana-operations/prod-operations.png): suggested slide “Historical production operations”. Shows original application/Argo/traffic panels. It also shows one critical alert; do not claim an all-green recovered environment or treat its charts as new local samples.

## Suggested presentation sequence

1. Existing architecture and historical PITR scope.
2. Current local isolation and PVC survival.
3. Recovery dependency startup and exact missing R2/registry inputs.
4. Actual Argo ConfigMap synchronization.
5. Actual monitoring metrics, restored dashboards and safe alert lifecycle.
6. Synthetic Jenkins restore with preserved encryption material and disabled jobs.
7. Actual workload and PostgreSQL logical rollback, with measured boundaries.
8. Scoped cleanup and the remaining requirements for a complete recovery exercise.

[Complete evidence index](astra-review/INDEX.md) · [Detailed report](LOCAL_DISASTER_RECOVERY_TEST_REPORT.md)
