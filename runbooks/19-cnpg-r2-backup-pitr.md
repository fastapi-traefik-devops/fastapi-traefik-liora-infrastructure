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

cert-manager is installed independently per cluster only for internal plugin
TLS. No application issuer/Certificate is created; Certbot and public traffic
remain unchanged. Plugin resources live with the CNPG operator in cnpg-system.
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
The coordinator has namespace-scoped Backup create/get/list and Cluster read,
plus read/update of its one precreated Lease. No live DB, Secret, Pod or PVC
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
