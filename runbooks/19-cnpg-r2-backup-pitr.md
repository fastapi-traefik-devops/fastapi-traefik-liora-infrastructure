# CNPG physical backups, R2 and isolated PITR

This procedure preserves current application data. The fresh-database disposal
authorization in runbook 18 does not apply. Use the existing pinned PostgreSQL
16 image and existing frontend/backend digests. No Jenkins CI build is required.

## Configuration and ownership

Bucket `liora-backup` is dedicated to this project and stays private. Each
namespace has its own ObjectStore and archive: `s3://liora-backup/dev/`, `stage/`,
`prod/`. One bucket-scoped S3 pair is shared; prefixes are not a security boundary.
Private credentials belong in ignored `recovery/recovery.yaml.database_backups`.
Never source the supplied text as shell code or print credential values.

Use supported Barman Cloud Plugin physical base backups plus continuous WAL,
lz4 for both. DEV/STAGE use 7d Barman recovery windows; PROD 14d. Preserve the
older anchor backup and required WAL. No independent R2 age-deletion rule.
An empty new archive does not establish a full historical recovery window.

The pinned per-cluster cert-manager also provides internal plugin TLS. Backup
installation does not create or alter public issuers/Certificates; those are
managed separately through [runbook 15](15-publish-application.md). Plugin
resources live with the CNPG operator in cnpg-system.
Environment ObjectStores/Clusters have their existing Argo ownership.

## Maintenance and installation

Record all application digest pairs, current data markers/schema, Secret/PVC
identities, Argo policies and approved Jenkins job/trigger states. Drain active
work, hold conflicting main/publication work and pause roots before children.
Use committed replica/rollout settings rather than imperatively fighting Argo.
Install the pinned dependencies, wait for internal certificates and plugin
readiness, then enable archiving one environment at a time. Sidecar changes may
roll databases. After the last database roll, declaratively refresh backend
connections as described in [runbook 18](18-cloudnative-pg.md), wait for real
rollouts, and verify login/CRUD with unchanged images. Readiness alone is not
application acceptance. Stop advancing on a failed checkpoint.

## Backup alert label contract

The coordinator ServiceMonitor endpoints use `honorLabels: true` so exported
`namespace="app-dev"`, `app-stage` and `app-prod` remain selectable by backup
rules rather than becoming `exported_namespace`. Verify actual Prometheus
samples after changing scrape configuration; a green target alone is insufficient.
The trusted exporter supplies only the environment labels defined by this project.

Direct coordinator alerts include the same `prometheus` identity as the native
Prometheus rules (`monitoring/monitoring-prometheus`), as well as cluster,
environment, namespace and severity. Keep these identities aligned if renaming
the monitoring release, or recovery/failure events may form duplicate alerts.
Failure, overdue and missing-data selectors have per-environment regression tests.

## Full backup coordinator

VM 250 owns a systemd timer at 02:00 UTC. It creates/observes CNPG Backup objects;
data goes directly from each cluster to R2. Order is PROD → STAGE → DEV.
A definitive failure is recorded/alerted without retry and permits the next
backup. Running/unknown state blocks the next environment and retains the
lock/evidence. API calls are bounded. No Kubernetes ScheduledBackup objects.

Use a local flock plus a non-expiring, resource-version guarded Kubernetes
coordination Lease to serialize hosts and recover intent after interruption.
Write the deterministic Backup name to durable intent before creation. A lost
POST response is resolved by observing that same object; do not create a new
backup on uncertainty. Never clear a held cycle merely because a timeout or
reboot occurred. An administrator must resume/inspect the recorded cycle.
The coordinator has namespace-scoped Backup create/get/list, plus read/update of its one precreated Lease. No live DB, Secret, Pod or PVC
write permissions. Private generated authentication/config stays recoverable
outside Git. Manual use from another administrator machine uses the same global
coordination protocol. VM 250 loss does not stop WAL or prevent PITR.

## Monitoring and objectives

Prometheus scrapes backup/coordinator and CNPG telemetry. Alertmanager receives
failure, overdue usable backup, WAL delay/error, missing telemetry and recovery
conditions; no daily success notification. Latest operator direction delegates
Slack setup/delivery to another person: verify Alertmanager integration only,
without claiming Slack receipt. Email is deferred.

Measure all bucket object pages and sum sizes for aggregate usage. Warn above
10 GiB; never stop backups or force-delete data. This is neither a quota nor a
claim that retention fits in 10 GiB. Verify recovery-window settings separately.
WAL archiving is independent of the coordinator; archive_timeout leaves headroom
inside RPO objectives of 15m PROD / 1h DEV-STAGE.

RTO objectives are 1h PROD / 4h DEV-STAGE, measured from available K3s/R2 access
through a usable restored application. Proxmox/K3s rebuilding is excluded.
Do not infer RPO/RTO compliance from configuration or a fresh archive alone.

## Isolated recovery verification

Run DEV, then STAGE, then PROD; at most one temporary restored instance.
Record a completed physical base backup. In the live source create a disposable
marker table/row, commit an included marker, select a UTC recovery target, then
commit an excluded marker later. Switch WAL and wait for successful archive
of the target and following commit. Retain evidence and clean only these markers.

Restore into a specifically named temporary namespace/Cluster. Use recovery
bootstrap and externalClusters plugin referencing the source server identity,
an explicit recoveryTarget time and the selected base backup. The restore
ObjectStore has **no retention policy**, and the restored Cluster has **no
WAL archiver plugin**. It can read the source archive but must not archive into
or clean it. Never switch live db Services or import live Argo tracking metadata.

Verify included marker present, excluded marker absent, ownership, extensions,
Alembic revision and existing-image application SQL/login/CRUD compatibility.
Measure wall time through usable application, archive delivery delay and what
was excluded. Retain non-secret evidence before deleting only the explicit
restore namespace/resources and their saved PVCs. Never delete live resources.

After all accepted checks, restore the exact saved Argo/Jenkins automation and
confirm unchanged live digest pairs, data, users/history and unrelated volumes.
No backup/recovery readiness claim until the corresponding PITR check passes.

## Recurring operator exercise

Once per month, manually initiate the same isolated DEV → STAGE → PROD PITR
procedure and record markers, target, backup ID, WAL evidence, measured RTO and
application compatibility. Repeat after significant backup mechanism changes.
Use one temporary instance at a time and the same explicit cleanup checks.
There is no automated weekly restore schedule.

## Operator commands and standalone files

From the reviewed original checkout with explicit kubeconfigs already available:

```sh
RECOVERY_PYTHON="$PWD/.local-work/venv/bin/python" bash recovery/check_credentials.sh --all --offline
bash scripts/local-python.sh scripts/backups/provision.py
```

Standalone provisioner: [provision.py](../scripts/backups/provision.py).
It derives R2 Secrets and namespace-scoped service-account profiles into ignored
`recovery/backup-coordinator.json`. API tokens/CA material are never printed.
Keep that file and the YAML inputs in protected recovery storage. Unknown state
is fenced in the PROD `app-prod/liora-backup-cycle` Lease, not only local files.

Install the pinned dependency paths independently per cluster (run only the
selected cluster's commands, and allow webhook readiness before plugin apply):

```sh
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-backup-platform -k kubernetes/platform/cert-manager
kubectl --kubeconfig="$kubeconfig" -n cert-manager rollout status deployment/cert-manager --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n cert-manager rollout status deployment/cert-manager-webhook --timeout=600s
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-backup-platform -k kubernetes/platform/barman-cloud
kubectl --kubeconfig="$kubeconfig" -n cnpg-system rollout status deployment/barman-cloud --timeout=600s
```

Sources, checksums and image pins: [cert-manager](../kubernetes/platform/cert-manager/UPSTREAM.md)
and [Barman plugin](../kubernetes/platform/barman-cloud/UPSTREAM.md).
The sidecar gets its endpoint through the standard AWS SDK `AWS_ENDPOINT_URL`
environment variable from the private R2 Secret; the account endpoint is not
copied into Git. Region is `auto`. Both source components use archive_timeout
300s. Requests/limits per sidecar are 50m/128 MiB and 500m/512 MiB.

VM 250 installation requires its trusted SSH host key in
`.local-work/private/phase10-2/known_hosts` and the existing recovery SSH identity.
It installs only `/opt/liora-backups`, `/etc/liora-backups`, its state and its
three systemd units. It preserves Tailscale and forwarding. The installer starts
read-only metrics but **does not activate the daily backup timer**:

```sh
bash scripts/backups/install-vm250.sh
```

Standalone installer: [install-vm250.sh](../scripts/backups/install-vm250.sh).
Runtime requirements are version/hash pinned. Coordinator memory/CPU limits are
128 MiB/50% of a CPU; metrics 256 MiB/50%. Its namespace-scoped persistent
service-account credentials are recoverable outside Git and cannot write Pods,
Secrets, PVCs, application Deployments or CNPG Cluster configuration.

On VM 250, inspect/run/resume using the same dedicated identity and global fence:

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py run
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py resume
```

Standalone coordinator: [coordinator.py](../scripts/backups/coordinator.py).
`resume` is explicit and refuses a fresh active owner; after interruption it
changes the session fence while retaining deterministic names and the cycle ID.
Do not run it concurrently merely to restart a healthy backup. A failed full
backup is terminal and is not retried. `--environment` is for single-environment
initial acceptance/ad-hoc work under the same fence; ordinary full cycles use
all three in strict PROD → STAGE → DEV order. No per-environment cron/timer.

Another trusted machine can run the coordinator with the private profile file
and `--state-dir /private/local/path`; VM 200 must not own the recurring timer.
Manual restore uses the administrator kubeconfigs, not this restricted identity.

After all three PITR and live application checks pass, enable the sole schedule:

```sh
sudo systemctl enable --now liora-backup.timer
systemctl list-timers liora-backup.timer
```

For initial or monthly PITR, choose a completed physical Backup name from the
matching namespace and run each sequentially. Do not proceed unless the previous
result says success and cleanup_complete. Use a new protected evidence directory:

```sh
bash scripts/local-python.sh scripts/backups/pitr.py --environment dev --backup "$dev_backup" --evidence "$evidence/dev"
bash scripts/local-python.sh scripts/backups/pitr.py --environment stage --backup "$stage_backup" --evidence "$evidence/stage"
bash scripts/local-python.sh scripts/backups/pitr.py --environment prod --backup "$prod_backup" --evidence "$evidence/prod"
```

Standalone PITR exercise: [pitr.py](../scripts/backups/pitr.py).
If copied elsewhere, use `--recovery-dir /private/recovery`. Operator tooling
requires the pinned local-tools and backup requirements plus the prepared
Chromium libraries. It uses unchanged frontend/backend images through a temporary
localhost proxy, checks real browser login/CRUD, and verifies actual image IDs.
The conservative RTO clock includes target/marker setup, WAL-upload confirmation,
namespace/database/app creation and browser acceptance. It excludes infrastructure
rebuild, image build, public routing changes and cleanup after usability.

The exercise retains failures. Never blindly delete namespaces after an error:
inspect the saved namespace UID/run ID, Cluster, PVC/PV names and source marker.
Cleanup is restricted to that exact `pitr-<env>-<run>` namespace and recorded
synthetic marker. Restored ObjectStores have no retention policy, and restored
Clusters have no WAL archiver plugin. Source credentials remain shared, so this
is configuration isolation rather than a read-only credential boundary.

Natural WAL delivery is measured separately from the PITR setup's forced switch:

```sh
bash scripts/local-python.sh scripts/backups/rpo.py start --environment "$environment" --record "$evidence/natural-rpo.json"
bash scripts/local-python.sh scripts/backups/rpo.py wait --environment "$environment" --record "$evidence/natural-rpo.json"
```

Standalone observer: [rpo.py](../scripts/backups/rpo.py), alongside `pitr.py` when
copied. It closes only the preceding segment before committing a marker. Do not
manually switch that marker's WAL or run a full backup for that environment
until observation completes. It records R2 LastModified delay and drops only
the matching table OID. A healthy five-minute sample is evidence, not a future
worst-case latency guarantee. Backup metadata alone does not prove RPO.

Install only the new monitoring resources, preserving other people's existing
Helm/Slack work. Their source is also linked from the monitoring kustomizations:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply --server-side --field-manager=liora-backup-monitoring -k kubernetes/platform/nonprod/backup-monitoring
kubectl --kubeconfig="$HOME/.kube/config-prod" apply --server-side --field-manager=liora-backup-monitoring -k kubernetes/platform/prod/backup-monitoring
```

VM 250 exports `/metrics/nonprod` and `/metrics/prod` on private TCP/9899, refreshed
every 60s and scraped every 30s. Usage sums all object pages with bounded calls;
a failed/partial scan reports stale telemetry rather than an incomplete total.
The 26-hour full-backup freshness margin is separate from the WAL RPO objective.
WAL errors and ready-WAL backlog use actual PostgreSQL archiver metrics. Primary
metric absence and coordinator/usage collection failures alert separately.
Alertmanager integration is verified independently of delegated Slack delivery.

Local checks (no Jenkins build or security scan):

```sh
python3 scripts/backups/tests/test_coordinator.py
bash scripts/local-python.sh scripts/backups/tests/test_metrics.py
bash scripts/local-python.sh scripts/backups/tests/test_pitr_safety.py
bash scripts/local-python.sh scripts/backups/tests/test_rpo_safety.py
bash scripts/local-python.sh scripts/backups/tests/check-rules.py --promtool .local-work/validation-tools/promtool
```

Rule checker: [check-rules.py](../scripts/backups/tests/check-rules.py). It extracts
native rule groups and checks firing/recovery fixtures using pinned promtool
3.15.0, whose release checksum was verified for this checkpoint.

Explicit cleanup of a failed exercise with an existing recorded namespace:

```sh
bash scripts/local-python.sh scripts/backups/pitr-cleanup.py --record "$evidence/dev/result.json"
```

Standalone cleanup: [pitr-cleanup.py](../scripts/backups/pitr-cleanup.py), alongside
`pitr.py`. It refuses a namespace UID/run mismatch. If interruption occurred
before namespace creation/UID recording, inspect the specific source marker
instead of inventing an identity or forcing deletion. Retain the failed result;
cleanup does not relabel a failed recovery as successful.

Alertmanager API-only verification (exact synthetic silence, no Slack test):

```sh
bash scripts/local-python.sh scripts/backups/test-alertmanager.py
```

Standalone script: [test-alertmanager.py](../scripts/backups/test-alertmanager.py).
It posts and resolves only its uniquely labeled synthetic alert and removes
only its own silence. It does not verify downstream notification delivery.
