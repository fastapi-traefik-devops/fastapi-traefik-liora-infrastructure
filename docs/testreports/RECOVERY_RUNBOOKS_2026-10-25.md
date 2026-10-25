# Live PostgreSQL and K3s datastore recovery procedures

Date: 2026-10-25 UTC.
Scope: runbooks 20/21, reusable preparation tools, private recovery-input capture
and local validation. No database restore, node restart, workload scaling,
GitOps policy change or remote push was performed.

## Starting state and available inputs

Both runbooks contained only TODO placeholders. The existing isolated PITR
script was not a live database recovery/cutover procedure. Existing Ansible
plays bootstrap fresh control planes and must not be used to restore etcd.

Read-only inspection found:

| Input | Result |
| --- | --- |
| Application/infrastructure checkouts | Original checkouts used; application working tree unchanged. |
| Database platform | Repository pins CNPG 1.30.1 and PostgreSQL 16.15 by image digest, with Barman ObjectStores and physical backup/WAL configuration. |
| R2 | Private inputs usable; four physical backup catalogs per environment. Latest completed physical IDs: DEV `20261025T020149`, STAGE `20261025T020057`, PROD `20261025T020007`. |
| K3s | Six Ready servers, `v1.36.5+k3s1`; two independent three-server datastores. |
| etcd snapshots | Existing local scheduled snapshots available in both clusters. |
| Server/node identity | Server tokens and node passwords readable through verified SSH. Optional local provisioning-token files were absent; a newly generated token is not a substitute for snapshot recovery. |
| Credentials | Application/database, R2 and SSH inputs remain private and ignored. No credential values were logged or added to Git. |

Protected sets were captured locally under ignored `recovery/etcd/`:

| Cluster | Snapshot | Local set |
| --- | --- | --- |
| NONPROD | `etcd-snapshot-k3s-1-01-1792929602` | `nonprod-20261025` |
| PROD | `etcd-snapshot-k3s-2-01-1792929601` | `prod-20261025` |

Each complete set contains the existing snapshot, token, three node passwords,
K3s version, cluster UID and SHA-256 manifest. File hashes and private permissions
passed verification. These are local copies, not an off-host backup service.
No new snapshot was created on a server.

## Implemented PostgreSQL procedure

Runbook 20 now covers target selection, matching credentials, empty-target gates,
physical backup/WAL replay, ownership/schema checks, prestart ordering, stable
`db` endpoint, unchanged application images, GitOps handover and backup release.

`prepare-live-restore.py` catalogs R2 independently of Kubernetes Backup objects
and prepares an environment-specific bundle. It refuses an existing CNPG Cluster
or PVC, active writers, invalid selection inputs and a nonempty new archive
prefix. The optional R2 provisioning action creates only a missing selected-env
Secret and refuses mismatches. Database manifests are never applied by this tool.

The bundle reads the selected source through an ObjectStore without retention
cleanup. Recovered WAL/base backups go to a separate new prefix and server
identity. Existing source data is not overwritten or pruned by the restored
cluster. The original instance count, resource/storage/placement settings and
frontend/backend image references remain unchanged.

`install-recovery-overlay.py` installs the bundle's source resource and **late
overlay patches** into one local overlay. This order matters: existing STAGE/PROD
overlay patches would override recovery values supplied by a Component. The
installer preserves other settings, checks the current image pair, refuses an
existing recovery directory and makes no cluster or remote Git writes.

PITR/RPO helpers now derive the active archive from the live WAL archiver and
ObjectStore instead of assuming the initial `<env>/liora-<env>/` identity. New
RPO observations record that identity and stop if it changes during measurement.

## Implemented etcd procedure

Runbook 21 covers integrity checks, complete server/runtime shutdown, original
identity installation, first-member snapshot reset, agentless API startup,
recovered workload holds, sequential peer rejoin and storage-gated release.

- `export-k3s-recovery.py` reads existing artifacts over verified SSH and creates
  an exclusive private set. A failed/partial export has no complete manifest.
- `verify-k3s-recovery.py` checks identity structure, checksums and private files.
- `hold-restored-workloads.py` requires the agentless first-server context and
  checks cluster UID. It saves original settings before changes, disables Argo
  automatic sync, scales Deployments/StatefulSets to zero, suspends Jobs/CronJobs
  and removes old workload Pod objects with UID preconditions. Explicit resume
  preserves the original state. PVCs/PVs, Secrets, namespaces and DaemonSets are
  not changed.

Etcd recovery does not restore local-path files. Lost PVC contents require their
own recovery source; the procedure stops consumers rather than initializing
empty directories. The fresh-cluster/R2 route remains the default full-host DR
path. A recovered metadata-only namespace with existing Cluster/PVC objects is
not an empty target for runbook 20.

## Validation

- Backup unit/safety suite: 31 tests; recovery tool suite: 4 tests.
- Tests cover all three bundle variants, source archive separation, unchanged
  image/instance/resource settings, live-target/writer refusal, error redaction,
  active archive selection and last-patch-wins GitOps installation.
- Recovery tests cover protected complete/partial exports, token disagreement,
  checksum failure, wrong-cluster refusal, saved original settings, explicit
  resume and UID-guarded mutations. Fixture credentials are excluded from output.
- Generated GitOps manifests render for DEV/STAGE/PROD. Strict schema validation
  uses the existing pinned CNPG/Barman/Certificate schemas and native Kubernetes
  schemas; all 15 resources per environment pass.
- A read-only preparation attempt against existing DEV exited 1 with an explicit
  existing Cluster/PVC refusal. No replacement bundle/database was applied.
- Captured recovery-set integrity checks pass for both clusters.
- Documentation links/anchors and shell code-block syntax are checked locally.

Commands:

```sh
bash scripts/local-python.sh -m unittest discover -s scripts/backups/tests -p 'test_*.py'
python3 -m unittest discover -s scripts/recovery/tests
python3 scripts/recovery/verify-k3s-recovery.py recovery/etcd/nonprod-20261025
python3 scripts/recovery/verify-k3s-recovery.py recovery/etcd/prod-20261025
```

## Remaining recovery work

- Execute live database recovery/cutover and three-server etcd restore in a
  separate agreed recovery checkpoint. Local checks do not establish original
  token/snapshot decryption, complete live cutover or recovered-volume usability.
- Select actual incident recovery points and compatible images/credentials at
  execution time. Catalog presence alone does not prove target WAL coverage.
- Copy the protected sets into the encrypted off-host kit and verify retrieval.
  Establish recurring off-host etcd snapshot capture; local scheduled snapshots
  alone do not cover loss of the Proxmox host.
- Complete the full-system DR exercise, including Terraform state/private kit,
  Jenkins stopped-home recovery and the monitoring-history coverage decision.
- Keep the prior Phase 9 promotion/acceptance work separate. No Jenkins jobs,
  polling, publication, PROD image-promotion gate or security scans changed here.

The earlier isolated PITR evidence remains in Phase 10.2. It is not relabeled as
a live recovery or full-system disaster recovery result.
