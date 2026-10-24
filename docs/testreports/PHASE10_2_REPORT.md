# Phase 10.2 — R2 physical backups and isolated PITR

Status: **completed on 2026-10-23**, within the agreed Alertmanager-only
notification boundary. Fresh CNPG installation is documented separately in
[Phase 10](PHASE10_REPORT.md); these current databases were preserved.

## Installed configuration

Both original checkouts were used. Infrastructure started at `14d73d0`;
application remained at `3459d5a4f1d39473fd845674dfc7f591bee81059`, clean.
Concurrent Slack commits were integrated with normal merge `971bce0`, without
rewriting history or replacing their monitoring configuration.

Existing CNPG 1.30.1 and PostgreSQL 16.15 remain unchanged. Both clusters now
have cert-manager 1.21.2 and Barman Cloud Plugin 0.15.1, with digest-pinned
controller/sidecar images and vendored upstream manifests. cert-manager handles
only CNPG/plugin internal certificates; existing public Certbot certificates,
DNS, routing and administrative endpoints were preserved.

cert-manager components each request 50m CPU/64 MiB and limit 500m/256 MiB.
Plugin controller requests 50m/128 MiB, limits 500m/256 MiB; injected sidecars
request 50m/128 MiB, limit 500m/512 MiB. DEV/STAGE retain one database instance
each; PROD retains two asynchronous instances on different nodes.

| Environment | Destination | Archive server | Recovery window |
|---|---|---|---|
| DEV | `s3://liora-backup/dev/` | `liora-dev` | 7 days |
| STAGE | `s3://liora-backup/stage/` | `liora-stage` | 7 days |
| PROD | `s3://liora-backup/prod/` | `liora-prod` | 14 days |

Base backups and WAL use lz4; `archive_timeout=300s`. Barman recovery-window
retention preserves the required anchor/WAL, with no independent age deletion
introduced. One supplied S3 credential pair is stored outside Git; prefixes do
not isolate credentials. Bucket HEAD/LIST/PUT/GET/DELETE succeeded. The owner
confirmed the bucket was empty and dedicated. Token verification succeeded,
but policy/public-access/lifecycle metadata APIs returned 403; those settings
and credential scope could not be independently audited. No permission or
bucket-policy changes were made.

## Backup coordinator and monitoring

VM 250 runs the recoverable systemd coordinator with hash-locked Python AWS
dependencies. It creates/observes Backup resources; data travels directly from
database Pods to R2. RBAC allows Backup get/list/create and a precreated named
PROD Lease get/update, without Secret reads, database changes or PVC deletion.
The durable nonexpiring global fence, local lock, persisted creation intent
and owner-session checks prevent timer/manual overlap and unsafe restart.
Terminal failure alerts and advances without retry; running/unknown state
blocks advancement and retains evidence.

The real complete cycle `55cbd7d042d948fabfc361d7498f7e44` completed in strict
order. A second invocation from the administrator host was refused while VM
250 held the global fence, without creating another cycle.

| Order | Backup resource | Physical backup ID | Completed UTC |
|---|---|---|---|
| PROD | `bk-55cbd7d042d948fabfc361d7-prod` | `20261023T154311` | 15:43:19 |
| STAGE | `bk-55cbd7d042d948fabfc361d7-stage` | `20261023T154358` | 15:44:11 |
| DEV | `bk-55cbd7d042d948fabfc361d7-dev` | `20261023T154448` | 15:44:57 |

The sole recurring timer is enabled on VM 250 at **02:00 UTC daily**; its first
scheduled invocation is 2026-10-24. No Kubernetes ScheduledBackup or VM 200
schedule was added. Metrics service and Tailscale remain active; forwarding
remains 1. Loss of the coordinator does not interrupt WAL archiving; manual
operation from another trusted host is documented.

All six new scrape targets are up; 15 NONPROD and 9 PROD rules are healthy.
Rules cover full-backup failure/overdue status, WAL failures/backlog, missing
telemetry, blocked/stale coordination, and aggregate usage/staleness.
All-page R2 enumeration measured **40,500,882 bytes in 53 objects**, approximately
38.6 MiB, after the accepted cycle. The warning threshold is 10 GiB, not a quota
or deletion trigger; this small initial sample does not predict retained size.

Both existing Alertmanagers accepted an exactly silenced synthetic firing
alert and its resolution; only those test silences were removed. Prometheus
Alertmanager discovery passed. Rule firing/recovery fixtures passed. Per the
latest operator instruction, Slack delivery/configuration is delegated and
was not investigated or claimed here. No daily success notification is sent.

## Isolated PITR and measured objectives

Exercises ran sequentially DEV → STAGE → PROD, one temporary one-instance
Cluster at a time, without switching live endpoints. Each used the explicit
physical backup below plus archived WAL. A table created after the base backup
contained an included marker before the selected target and an excluded marker
after it; recovered contents demonstrated the boundary. Restored configuration
had no source-archive writer or retention cleaner.

| Environment | Physical backup ID | Recovery target UTC | App usable / RTO objective | Natural WAL delivery / RPO objective |
|---|---|---|---|---|
| DEV | `20261023T135047` | 13:54:33.341887 | 286.163s / 4h | 303.059s / 1h |
| STAGE | `20261023T140627` | 14:10:38.064581 | 195.483s / 4h | 304.031s / 1h |
| PROD | `20261023T142102` | 14:27:18.292025 | 287.029s / 1h | 304.043s / 15m |

RTO begins with working K3s/R2 access and includes marker preparation, WAL
availability, temporary namespace/database startup and usable application.
It excludes infrastructure rebuilding and cleanup after application usability.
PITR archive switches arrived in 4.326/6.641/4.361 seconds respectively, but
these forced switches are **not** the natural RPO samples. Separate RPO probes
measured acknowledged commit to the containing WAL object's R2 timestamp,
without switching that measured segment manually.

All restores retained database `app`, owner `app_owner`, non-superuser app
role, PostgreSQL 16.15 and Alembic head `1a31ce608336`. Temporary frontend and
backend used each environment's existing image digests. Real browser login
and disposable create/read/update/delete checks passed. STAGE/PROD restored
extension checks included `plpgsql` and `uuid-ossp`; the DEV restored exercise
did not record a separate extension query. Source user/item counts and fingerprints matched
before/after. Explicit temporary namespace UID guards, namespace disappearance
and temporary PV removal were checked; all source markers were removed.

These successful small-lab measurements meet the stated objectives for the
observed samples, not a worst-case guarantee. The new archive has not yet aged
through a complete 7/14-day recovery window. Monthly manually initiated
sequential PITR, also after significant mechanism changes, is documented in
[runbook 19](../../runbooks/19-cnpg-r2-backup-pitr.md).

## Preservation, automation and validation

Each environment was paused declaratively before database sidecar rollout,
then frontend/backend replicas restored with an explicit backend reconnect
rollout using unchanged images. Live HTTPS browser login/CRUD passed in all
three environments before releasing the maintenance hold.

Final checks preserved all **13 original PVC UIDs/PVs**, application/database,
image-pull, public TLS and Jenkins Secrets, current application data and image
references. Concurrent monitoring Secret changes belong to the separately
recorded Slack deployment and were preserved. Jenkins administrator identity,
job enablement, triggers, build counts and retained controller state matched
the saved baseline. Main and trusted publisher were restored, with main polling
`H/2 * * * *`; the already-approved PR-65 job was left untouched. No unrelated
imported jobs or schedules were enabled. All five Argo applications are
Synced/Healthy with their original automation policies restored.

Local validation passed: 12 coordinator tests (including failed backup,
unknown/running state, interruption/resume and session fencing), 4 metrics
tests, 2 PITR safety tests, 3 RPO safety tests, 20 recovery-schema/secrecy tests,
and 24 native Prometheus rule checks plus firing/recovery fixtures. RBAC
positive/negative checks passed. Credential validation/output tests and tracked
content checks do not expose fixture or operator secret values.

During implementation, the coordinator ServiceMonitor was corrected to use
EndpointSlice discovery; a local RPO watcher OID string comparison and benign
browser disconnect/proxy shutdown handling were corrected. Original diagnostic
evidence remains; these are not relabeled as database recovery failures.

No full Jenkins CI/CD regression, image rebuild/publication, vulnerability
scan, failover or host-reboot exercise was performed. Phase 9 delegated work,
automatic STAGE acceptance and its PROD image-promotion gate remain pending;
`PROD_ENABLED=False` remains unchanged. Backup verification does not satisfy
that separate application-release gate.

Key implementation commits include `bcc240b` (dependencies), `ed69e0a`
(coordinator/archive primitives), `638976d` and `aaba125` (monitoring),
`c173f82` (guarded operator procedures), and `d7cbc85` (desired architecture).
Private detailed evidence is retained under `.local-work/private/phase10-2/`;
credentials and generated coordinator access remain in ignored `recovery/`
files, outside Git. Monthly restore exercises, accumulated retention-window
coverage and delegated notification/release work remain ongoing operations.


## Subsequent scheduled-backup confirmation

The owner confirmed that the automatic overnight backup run produced new
archives in the project's R2 bucket. This provides operator-observed evidence
of scheduled backup output after the initial implementation and timer setup.

This confirmation did not include per-environment Backup identifiers, coordinator
logs or terminal-state records, so it is not presented as an independently
reviewed PROD → STAGE → DEV cycle. It is also not an additional PITR exercise
or proof of accumulated 7/14-day recovery-window coverage. The previously
recorded isolated restore results remain the recovery-verification evidence.
No live backup, R2 or coordinator settings were changed during this update.
