# K3s etcd snapshot backups

**Where:** Operator machine, infrastructure repository root. Use Tailscale for node and monitoring access.
**Purpose:** Keep an off-host copy of each cluster's Kubernetes datastore.
**Recovery route:** Standard disaster recovery rebuilds the clusters and restores application data. Etcd restore is optional and manual; use [runbook 21](../../runbooks/21-restore-k3s-etcd-snapshot.md).

## Backup scope

| Data | Backup source | Coverage |
| --- | --- | --- |
| Kubernetes datastore | Native K3s snapshots in R2 | Kubernetes objects, Secrets, RBAC and controller state at the snapshot time. No PVC file contents. |
| Application PostgreSQL | Barman physical backups and continuous WAL in R2 | Database rows, schema, roles and a selected recovery point. Follow [19](../../runbooks/19-cnpg-r2-backup-pitr.md) and [20](../../runbooks/20-restore-live-postgresql.md). |
| Jenkins | Stopped-controller home archive and mounted configuration | Administrator, encryption keys, jobs, credentials and retained history. Follow [23](../../runbooks/23-restore-jenkins-controller.md). Etcd and PostgreSQL snapshots do not contain this home directory. |
| Private recovery inputs | Encrypted off-host recovery kit | Original server tokens, node passwords, SSH/API credentials, application inputs, encryption keys and infrastructure state. Follow [recovery inputs](../../recovery/README.md). |
| Monitoring and other PVCs | Separate volume/data protection | This procedure does not copy their contents. Preserve surviving volumes. Rebuilding monitoring starts new history unless a separate archive is available. |

Treat etcd snapshots as sensitive: they contain cluster Secrets. Keep the bucket
private. Do not publish a snapshot or its download directory.

## Schedule and retention

All node clocks use UTC. Native K3s runs on each server; VM 250 does not schedule
or transport etcd snapshots. PostgreSQL backups start independently at 02:00 UTC.

| Cluster | Nodes | Snapshot times UTC | R2 prefix |
| --- | --- | --- | --- |
| NONPROD | k3s-1-01 / -02 / -03 | 03:00 / 03:02 / 03:04 and 15:00 / 15:02 / 15:04 | `s3://liora-backup/etcd/nonprod/` |
| PROD | k3s-2-01 / -02 / -03 | 03:10 / 03:12 / 03:14 and 15:10 / 15:12 / 15:14 | `s3://liora-backup/etcd/prod/` |

- Local: five scheduled snapshots **per node** in `/var/lib/rancher/k3s/server/db/snapshots/`.
- R2: 42 snapshot files **per cluster prefix**, across all three nodes. At six files per day, this is about seven days. It is a count limit, not a guaranteed recovery window.
- Compression: native K3s ZIP. Metadata sidecars do not count as snapshot files.
- Manual snapshots made with the normal `etcd-snapshot` name consume the same retention count.
- Native K3s prunes this snapshot-name prefix only. PostgreSQL prefixes and WAL are separate. Do not add bucket-wide lifecycle rules.
- Etcd failures do not block PostgreSQL backups or WAL. Losing VM 250 stops freshness telemetry, but node snapshot scheduling continues.

## Configure or reapply native backups

### Preconditions

- [ ] Prepare [operator tools](../../runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
- [ ] Validate `recovery/recovery.yaml`. Reuse its bucket-scoped `database_backups` S3 pair; no new recovery fields are required.
- [ ] Confirm the bucket is private in Cloudflare: **R2 → liora-backup → Settings → Public access**. Require the managed public URL disabled and no enabled public custom domains. Do not change unrelated buckets or domains.
- [ ] Confirm all three nodes in the selected cluster are Ready.
- [ ] Preserve the matching token/node recovery set outside the Proxmox host before planned node maintenance; use the [identity capture procedure](../../recovery/README.md#k3s-server-tokens-and-recovery-identities) only. Do not run its restore steps.
- [ ] Set a verified SSH host-key file. Do not use `site.yml` for this change.

### Apply one cluster

- [ ] Select the inventory and private kubeconfig:

```sh
cluster=nonprod
case "$cluster" in
  nonprod) inventory=infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml; kubeconfig="$HOME/.kube/config-dev-stage" ;;
  prod) inventory=infrastructure/k3s-cluster/ansible/inventory-prod.yml; kubeconfig="$HOME/.kube/config-prod" ;;
  *) exit 1 ;;
esac
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
```

- [ ] Apply the standalone playbook with your verified SSH configuration:

```sh
.local-work/venv/bin/ansible-playbook -i "$inventory" \
  --private-key recovery/LIORA-id_ed25519 \
  -e 'ansible_ssh_common_args="-o StrictHostKeyChecking=yes -o UserKnownHostsFile=/home/root-admin/.ssh/known_hosts"' \
  infrastructure/k3s-cluster/ansible/60_etcd_r2.yml
```

Standalone playbook: [60_etcd_r2.yml](../../infrastructure/k3s-cluster/ansible/60_etcd_r2.yml).

Use the actual verified host-key file path. The playbook checks node names,
version, UTC and Ready status. It creates `kube-system/k3s-etcd-r2`, writes only
`config.yaml.d/90-etcd-r2.yaml`, and restarts one server at a time **only if that
file changes**. It waits for API and node readiness before moving on.

**Stop:** Any task fails or quorum/node readiness is lost. Keep the other nodes
running. Inspect the affected server with `sudo journalctl -u k3s`. Do not reset
etcd, stop all servers or alter database PVCs.

- [ ] Finish NONPROD checks below before repeating for PROD.
- [ ] Retain `etcd-s3` and `etcd-s3-config-secret` as the only S3 options in node configuration. Other S3 flags override Secret-based configuration. The retention, endpoint and timeout are fields in the Secret.
- [ ] After credential rotation, reapply the playbook. Do not print the Secret; credentials are read from it for snapshot operations.

## Create and inspect a snapshot

**Where:** Root shell on one selected server.

- [ ] Create a snapshot using the scheduled name prefix:

```sh
sudo /usr/local/bin/k3s etcd-snapshot save --name etcd-snapshot
sudo /usr/local/bin/k3s etcd-snapshot ls
```

- [ ] Require both a local file and `s3://liora-backup/etcd/<cluster>/...` for the new snapshot. Command exit status alone does not prove upload.
- [ ] From the operator checkout, confirm the object directly in R2:

```sh
bash scripts/local-python.sh scripts/backups/etcd_r2.py list --cluster "$cluster"
```

Standalone tool: [etcd_r2.py](../../scripts/backups/etcd_r2.py).

## Download and check integrity

**Where:** Operator checkout. Use a new private output directory.

- [ ] Select the `name` field from the R2 list, then download:

```sh
read -r -p 'Exact snapshot filename: ' snapshot
output="$PWD/.local-work/etcd-download-$cluster-incident-1"
bash scripts/local-python.sh scripts/backups/etcd_r2.py download \
  --cluster "$cluster" --snapshot "$snapshot" --output "$output"
```

Standalone tool: [etcd_r2.py](../../scripts/backups/etcd_r2.py).

**Expected:** Exit 0, `zip_crc_and_etcd_sha256: true`, and a SHA-256 for the
compressed file. The command starts no etcd process and performs no restore.

**If a check fails:** Keep the downloaded file and diagnostic identifiers private.
Select another retained snapshot. Do not use a failed file for recovery. Follow
[21](../../runbooks/21-restore-k3s-etcd-snapshot.md) only after selecting the optional restore route.

## Monitor and handle failures

- [ ] Open the selected cluster's Prometheus through Admin VIP `.16` or `.17`, port `9090`.
- [ ] Check `liora_etcd_r2_latest_snapshot_timestamp` and the R2 object list.
- [ ] Check `k3s_etcd_snapshot_save_s3_duration_seconds_count{job="apiserver",status="success"}` for successful uploads.

| Alert | Condition | Action |
| --- | --- | --- |
| `K3sEtcdSnapshotFailed` | Native creation/upload error observed in the last 30 minutes; held for 2 minutes | Inspect the affected node's K3s journal. Check disk space, the S3 Secret reference, endpoint reachability and credentials. Create one new snapshot after fixing the cause; verify its R2 object. |
| `K3sEtcdSnapshotR2Stale` | No confirmed snapshot within 14 hours, no object, or missing freshness metric; held for 5 minutes | Check node scheduler/configuration, VM 250 telemetry and direct R2 access. Do not interpret missing telemetry as healthy backups. |
| Existing collector/R2 telemetry alerts | VM 250 cannot collect or list the bucket | Recover `liora-backup-metrics.service` using [19](../../runbooks/19-cnpg-r2-backup-pitr.md). Snapshot creation on the nodes remains independent. |

Failure alerts clear when the error window passes; confirm a new R2 object before
closing an incident. Existing Alertmanager receivers send firing and resolved
notifications. No daily success notifications are configured.

The existing VM 250 collector derives freshness from its bucket listing; it adds
no scheduler. It excludes sidecars, empty objects and wrong-cluster filenames.
Re-uploading an old snapshot does not reset its content age. Aggregate 10-GiB
usage monitoring includes both PostgreSQL and etcd objects.

- [ ] To update only this collector code, run:

```sh
bash scripts/backups/install-vm250.sh --metrics-only
```

Standalone installer: [install-vm250.sh](../../scripts/backups/install-vm250.sh).

- [ ] Apply scoped rules after deploying the collector:

```sh
kubectl --kubeconfig="$kubeconfig" apply -k "kubernetes/platform/$cluster/backup-monitoring"
```

## Preserve tokens and recovery inputs

- [ ] Keep the current original tokens at `recovery/k3s-nonprod-server.token` and `recovery/k3s-prod-server.token`, mode `0600`. Include these and matching node metadata in your existing encrypted recovery archive; keep the archive off-host. Use [recovery sets](../../recovery/README.md#k3s-server-tokens-and-recovery-identities).
- [ ] Before rotating a server token, retain its old set for every snapshot that still needs it.
- [ ] After rotation or K3s upgrade, [capture new identity metadata](../../recovery/README.md#k3s-server-tokens-and-recovery-identities). Create and inspect new R2 snapshots, then update the encrypted kit before retiring any old token.
- [ ] Use the existing `recovery/make_recovery_backup.sh` workflow. Keep its password separate from the kit. Do not copy a token for every snapshot or store raw tokens in R2/Git.
- [ ] Keep snapshots on the nodes and in native R2 prefixes. Use private `.local-work/` directories for disposable downloads; never use `recovery/` for snapshot files.
- [ ] During optional recovery, use the token that matches the selected snapshot, not a newly generated bootstrap token. The download helper can check the snapshot's cluster/token metadata when assembling the recovery set; this is not a restore/decryption exercise.

## Reference

[Native K3s snapshot/S3 configuration](https://docs.k3s.io/cli/etcd-snapshot),
[pinned S3 retention implementation](https://github.com/k3s-io/k3s/blob/v1.36.5%2Bk3s1/pkg/etcd/s3/s3.go),
[pinned Secret configuration](https://github.com/k3s-io/k3s/blob/v1.36.5%2Bk3s1/pkg/etcd/s3/config_secret.go).
