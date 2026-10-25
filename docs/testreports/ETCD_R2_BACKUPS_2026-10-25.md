# Native K3s etcd snapshots to R2

Date: 2026-10-25 UTC.

## Scope and design

The original infrastructure checkout was used. Existing recovery scripts and
three local recovery commits were preserved. The application checkout was not
changed. No etcd reset/restore, cluster rebuild, application build, image
publication, PVC deletion, GitHub permission change or bucket lifecycle change
was performed.

Native K3s snapshot scheduling and S3 upload are used directly. There is no new
backup scheduler, notification service or dependency on the PostgreSQL cycle.
VM 250's existing read-only bucket enumeration supplies the one missing
observation: actual snapshot freshness in R2.

## Preflight and configuration

- All six servers run `v1.36.5+k3s1` and use UTC. Their previous local snapshot
  configuration used the native defaults: twice daily and five files per node.
- Native snapshot metrics were already scraped through `job="apiserver"`.
  Duplicate kubelet copies were excluded from the new alert expressions.
- Existing bucket-scoped credentials passed HEAD plus PUT/LIST/GET/DELETE under
  unique temporary keys in **each** etcd prefix. Those probe objects were removed;
  PostgreSQL backups and WAL were not changed.
- Existing R2 YAML fields are reused unchanged. The later fixed-token file
  contract adds secure-token file validation and visibly fake examples. S3 credentials are in `kube-system/k3s-etcd-r2`, not Git
  or process arguments. The node drop-in references that Secret only.
- Ansible Core `2.19.4` was installed in the existing operator venv and pinned in
  local-tool requirements. No new dependencies were installed on K3s servers or VM
  250 for snapshot handling.

| Cluster | Nodes / UTC cron minutes at 03:xx and 15:xx | Destination |
| --- | --- | --- |
| NONPROD | `k3s-1-01`: 00; `-02`: 02; `-03`: 04 | `s3://liora-backup/etcd/nonprod/` |
| PROD | `k3s-2-01`: 10; `-02`: 12; `-03`: 14 | `s3://liora-backup/etcd/prod/` |

The hour gap after the existing 02:00 PostgreSQL cycle and node/cluster staggering
reduce normal simultaneous load. Snapshot execution does not wait for PostgreSQL
success; PostgreSQL/WAL do not wait for etcd.

Local retention remains five snapshots per server. Native ZIP compression is
enabled. R2 retains **42 snapshot files across a cluster prefix**, approximately
seven days at six scheduled files/day. This is count-based, not a recovery-window
guarantee. Manual snapshots with the scheduled prefix also consume the count.
Metadata sidecars are excluded by native retention. The pinned implementation
lists the configured folder/name prefix globally; it does not retain 42 per node.
No bulk retention deletion was induced merely to test the limit.

The standalone `60_etcd_r2.yml` playbook configured NONPROD, then PROD. It checked
node names/version/UTC/membership and Ready status, restarted **one** server at a
time, and required local API and all-node readiness before advancing. Only its
new snapshot drop-in triggered restarts. The original token/configuration and
Pod processes were preserved.

## Controlled uploads and integrity

| Cluster | Snapshot | Bytes | Compressed-file SHA-256 |
| --- | --- | ---: | --- |
| NONPROD | `etcd-snapshot-k3s-1-01-1792939090.zip` | 4,277,390 | `13a1d5e4f5eb9c78d46e448f3366c1d7136b05dce6b39a44a505e258177152a8` |
| PROD | `etcd-snapshot-k3s-2-01-1792939379.zip` | 3,478,280 | `4b3f56055d8546468ec7dac01a117a3f184f791367877124860c3fd5d7e296a6` |

The uploads completed at 14:38:12 UTC and 14:43:01 UTC respectively. Each object
was downloaded using the existing authenticated R2 endpoint. ZIP CRC and the
embedded etcd SHA-256 passed; the compressed-file hash matched the corresponding
node-local file. R2 cluster/token metadata matched the protected original
identity set. Initial complete verification sets were assembled privately under ignored
`recovery/etcd-r2-downloads/` and passed the recovery-set verifier. The later
owner-directed layout and cleanup below removed those temporary copies.

`etcd_r2.py` performs list/download/check operations only. It cannot restore or
delete an etcd snapshot. Its optional identity attachment preserves the original
set, rejects a mismatching cluster/token, and writes a new set with the downloaded
snapshot's checksum. Download and identity checks do **not** establish successful
restoration, bootstrap-data decryption or application recovery.

## Native recurring operation

Without changing cron or issuing further snapshot commands, all six servers uploaded:

| Node | Scheduled snapshot | R2 upload time UTC |
| --- | --- | --- |
| k3s-1-01 | `etcd-snapshot-k3s-1-01-1792940404.zip` | 15:00:06.825 |
| k3s-1-02 | `etcd-snapshot-k3s-1-02-1792940525.zip` | 15:02:08.562 |
| k3s-1-03 | `etcd-snapshot-k3s-1-03-1792940643.zip` | 15:04:06.277 |
| k3s-2-01 | `etcd-snapshot-k3s-2-01-1792941005.zip` | 15:10:07.399 |
| k3s-2-02 | `etcd-snapshot-k3s-2-02-1792941124.zip` | 15:12:06.753 |
| k3s-2-03 | `etcd-snapshot-k3s-2-03-1792941242.zip` | 15:14:03.668 |

These are the configured recurring runs, distinct from the earlier controlled
uploads. Snapshot scheduling continues inside K3s and does not use a VM 250 timer.

## Monitoring

Each cluster has two new scoped rules, loaded and healthy in live Prometheus:

- `K3sEtcdSnapshotFailed`: native creation/upload error in a 30-minute window,
  with a two-minute hold. First appearance of a nonzero error counter is covered,
  not just later increments. It clears when that error condition ages out.
- `K3sEtcdSnapshotR2Stale`: no confirmed snapshot within 14 hours, an empty prefix
  or an absent freshness metric, held for five minutes.

The VM 250 collector reuses its complete paginated usage scan. It excludes
metadata, empty objects and wrong-cluster filenames, and uses the older of object
upload time and the timestamp in the snapshot name. Re-uploading an old snapshot
cannot make it fresh. Existing collector/R2 telemetry alerts remain in place;
last known snapshot time is retained if enumeration fails.

Only `metrics.py` and its service were updated on VM 250 using `--metrics-only`.
Coordinator code and private configuration hashes remained equal; the existing
02:00 timer and Tailscale service remained active. No coordinator journal or
PostgreSQL serialization logic was changed. Aggregate 10-GiB usage monitoring now
also includes etcd objects.

Both Prometheus instances discover their Alertmanager. Existing normal receivers
have recovery notifications enabled. No daily success notification or synthetic
Slack message was sent; unrelated Slack behavior was not investigated.

## Local checks and protected state

- Backup/operator tests: **40 passed**. Recovery identity/set/hold tests: **6 passed**. Private-input validator tests: **22 passed**.
- New cases cover prefix-scoped listing, pagination/freshness, sidecar/empty/wrong
  node exclusion, stale-to-fresh and first-error-to-recovered expressions,
  embedded checksum rejection, and token mismatch before copying credentials.
- Both Ansible inventory syntax checks pass. Changed Python parses; operator
  shell blocks and installer syntax pass. Documentation links/anchors pass.
- Before/after comparison retained the same protected application/database/Jenkins
  Pod/controller/PVC UIDs, images and Secret hashes at the backup-rollout
  checkpoint, before the later concurrent STAGE promotions. Running containers
  started before this maintenance. Database contents were not modified by this task.
- HTTPS through private edge `.240`, with each canonical hostname and certificate
  validation, returned 200 for DEV, STAGE and PROD. Direct public-IP access from
  this operator host returned connection refused; external public reachability
  was not established by that check. No routing or certificates changed.
- Unauthenticated requests to the S3 object endpoint were rejected (HTTP 400).
  Existing credentials could not read Cloudflare managed/custom public-domain
  settings through the management API. Those settings were not changed, and this
  report does not claim an independent public-domain audit.

## Recovery scope and documentation

Standard DR explicitly remains fresh infrastructure/platform deployment followed
by application-data restoration and verification. Runbook 21 is an optional
manual route. It can download a matching R2 snapshot and suppresses native
snapshot scheduling during datastore restoration; re-enablement follows storage
and application checks. No restore command was executed here.

Etcd contains Kubernetes objects/Secrets, not PVC files. PostgreSQL physical
backups/WAL, Jenkins stopped-home archives, private keys/state and other volume
contents remain distinct recovery sources. Ongoing Jenkins/full-system recovery
work is not completed by these snapshots.

## Fixed-token layout and scoped cleanup

The owner's final decision superseded the proposed separate off-host destination
and password-file request. The existing `recovery/make_recovery_backup.sh`
workflow owns encrypted archive creation; the owner keeps its copy outside the
host. No new destination, password file or archive service was configured. The
owner-provided helper was inspected and left unchanged. It was committed
independently during this task as `85e02f4`.

The current actual server tokens were read from all three nodes of each cluster
without generation or rotation. Matching values are stored once at:

- `recovery/k3s-nonprod-server.token` — mode `0600`, Git-ignored.
- `recovery/k3s-prod-server.token` — mode `0600`, Git-ignored.

Node passwords, cluster UID/version and token checksums are retained in private
`recovery/k3s-identities/nonprod-20261025/` and `prod-20261025/`. These directories
contain no snapshots and no duplicate token files. The identity-only exporter
and verifier passed against the fixed tokens. The existing archive helper's
untracked-file selection includes both fixed files and these metadata inputs.
The owner is responsible for creating the updated encrypted archive and keeping
its off-host copy; no completed archive transfer is claimed here.

Fresh installation's kubeconfig-fetch play now saves the actual server token at
the fixed path, mode `0600`. It refuses a differing previous token. Setup docs
preserve old tokens before replacing a cluster; rotation docs retain historical
tokens for snapshots that still require them. The validator checks supplied
secure-token format and permissions; visibly fake file examples accompany it.
Current private inputs pass with zero errors and two existing legacy-X509 CA
warnings. Those original CAs were retained.

The owner authorized removing the earlier local snapshot copies/verification
bundles from `recovery/`. After preserving and checking the fixed tokens and
canonical node identities, an allowlisted cleanup removed **25 files totaling
66,011,101 bytes**, including five snapshot copies. Duplicate credentials were
removed only after byte comparison with the retained inputs. Metadata was checked
against the canonical cluster/token identity before removal. Other keys, inputs,
archives and the owner's helper were not changed. The cleanup never contacted
nodes or R2 and deleted no remote snapshots.

The historical standalone [cleanup script](cleanup-etcd-recovery-copies-20261025.py)
contains the exact target allowlist and preservation guards; default operation is
inspection. Private file/hash evidence is in
`.local-work/etcd-r2/cleanup-evidence.json`. No etcd snapshot files remain anywhere
under `recovery/`. Download/export tools now refuse such destinations. Routine
verification uses `.local-work/` without token copies; an incident restore bundle
may attach a matching fixed/historical token only when that optional route is
selected. The new failure/refusal tests contain credential canaries and confirm
that errors do not print their values.

## Remaining work

The owner must refresh and store the encrypted private-input archive outside the
host using the existing helper. Snapshot creation/upload, normal recurring
operation, integrity checks and alert configuration are complete. Restoration
was not performed. Full-system DR and the separately planned recovery exercises
remain separate work; checksum success is not restoration evidence.


## Concurrent repository changes

While this work ran, upstream advanced with Jenkins publisher pinning, Phase 9
status updates, DR evidence relocation and STAGE promotions for application
`bad88a611b5c`. Those commits were preserved through a normal merge of upstream
`46fddd1`; no history was rebased, squashed or force-pushed. The later STAGE image
changes belong to that concurrent CI/CD work, not this backup task. The merged
application overlays and Jenkins definitions retain the upstream versions.
The owner also independently committed the unchanged encrypted-archive helper
as `85e02f4`; its source hash remained unchanged during this backup work.
