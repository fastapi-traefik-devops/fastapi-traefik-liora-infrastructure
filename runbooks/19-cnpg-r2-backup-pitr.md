# Install and operate PostgreSQL backups

**Where:** Management VM 200 for Kubernetes commands; VM 250 for the
backup coordinator.

**Scope:** Physical base backups and continuous WAL archiving. Preserve application data and image digests.

## Configuration reference

| Environment | Namespace / cluster | R2 destination | Archive identity | Window | RPO / RTO objective |
| --- | --- | --- | --- | --- | --- |
| DEV | app-dev / NONPROD | `s3://liora-backup/dev/` | liora-dev | 7 days | 1 hour / 4 hours |
| STAGE | app-stage / NONPROD | `s3://liora-backup/stage/` | liora-stage | 7 days | 1 hour / 4 hours |
| PROD | app-prod / PROD | `s3://liora-backup/prod/` | liora-prod | 14 days | 15 minutes / 1 hour |

Use Barman recovery-window retention, including the older anchor backup and WAL.
Do not configure independent age-based R2 deletion. Both base backups and WAL use
lz4; `archive_timeout=300s`. RTO starts with working K3s/R2 access and ends with
a usable restored application; infrastructure rebuild time is excluded.

The bucket is private. One bucket-scoped S3 pair covers all prefixes; prefixes
are not credential isolation. Database backup data travels directly between
clusters and R2. WAL archiving does not depend on VM 250.

## 1. Install backup dependencies and access

### Install platform operators in either scenario

- [ ] Confirm explicit kubeconfigs, selected revision and capacity.
- [ ] Before modifying an existing database, record its digest pair and data/credential identities. Drain conflicting delivery work and hold Argo roots before children.
- [ ] Install the pinned CNPG operator using [runbook 18](18-cloudnative-pg.md#1-install-the-operator).
- [ ] Install the following independently in each cluster. Start with NONPROD,
      confirm its API identity, then repeat with `config-prod`:

```sh
kubeconfig="$HOME/.kube/config-dev-stage"  # Repeat with config-prod after NONPROD succeeds.
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-backup-platform -k kubernetes/platform/cert-manager
kubectl --kubeconfig="$kubeconfig" -n cert-manager rollout status deployment/cert-manager --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n cert-manager rollout status deployment/cert-manager-webhook --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n cert-manager rollout status deployment/cert-manager-cainjector --timeout=600s
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-backup-platform -k kubernetes/platform/barman-cloud
kubectl --kubeconfig="$kubeconfig" -n cnpg-system rollout status deployment/barman-cloud --timeout=600s
```

Pins and resource budgets: [cert-manager](../kubernetes/platform/cert-manager/UPSTREAM.md),
[Barman plugin](../kubernetes/platform/barman-cloud/UPSTREAM.md).

### Provision R2 access for a fresh database

This section applies only to a fresh database. During disaster recovery,
return to the [recovery checklist](../01-Disaster_recovery.md) after installing
the operators. Use the selected backup and matching credentials in the
[live database restore runbook](20-restore-live-postgresql.md).

- [ ] Prepare `database_backups` in ignored `recovery/recovery.yaml`; see the [input schema](../recovery/README.md#database-physical-backup-r2-inputs).
- [ ] Create all three application namespaces before running the all-environment provisioner. Do not create database Clusters yet on a fresh installation.
- [ ] Validate inputs and provision access:

```sh
bash recovery/check_credentials.sh --all --offline
bash scripts/local-python.sh scripts/backups/provision.py
```

Standalone script: [provision.py](../scripts/backups/provision.py).

- [ ] Preserve generated `recovery/backup-coordinator.json` privately. On rebuilt clusters, retain the old profile and replace it only after reviewing the new cluster CA/token identities.
- [ ] Check the intended archive destination before initializing a new database. Stop if it contains another database's archive; preserve existing backups and select the recovery procedure instead.
- [ ] Apply each environment's ObjectStore before its Cluster through the selected deployment procedure.
- [ ] Require CNPG Ready and `ContinuousArchiving` healthy; inspect backup sidecar events/logs on failure.
- [ ] After database rolls, complete the reconnect/login/CRUD checks in [runbook 18](18-cloudnative-pg.md#database-maintenance), then restore the recorded automation.

## 2. Install the coordinator on VM 250

- [ ] Confirm Tailscale routing is active and the VM 250 SSH host key is trusted.
- [ ] From VM 200, collect VM 250's SSH host key:

```sh
umask 077
mkdir -p .local-work/private/phase10-2
ssh-keyscan -t ed25519 192.168.77.250 > .local-work/private/phase10-2/known_hosts.candidate
ssh-keygen -lf .local-work/private/phase10-2/known_hosts.candidate
```

- [ ] Through the trusted Proxmox VM console, compare that fingerprint with
      `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on VM 250. Only after
      they match, install the scanned key:

```sh
mv .local-work/private/phase10-2/known_hosts.candidate .local-work/private/phase10-2/known_hosts
```

Do not disable host-key verification. The installer requires the resulting
`.local-work/private/phase10-2/known_hosts` path.
- [ ] Install coordinator source, pinned dependencies, private configuration and systemd units:

```sh
bash scripts/backups/install-vm250.sh
```

Standalone script: [install-vm250.sh](../scripts/backups/install-vm250.sh).

The installer starts metrics and preserves Tailscale/forwarding. It does not
enable the backup timer. Coordinator API access is limited to Backup creation/
observation and its named global coordination Lease.

- [ ] On VM 250, inspect state and run one coordinated cycle:

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py run
```

Standalone script: [coordinator.py](../scripts/backups/coordinator.py).

- [ ] Require strict PROD → STAGE → DEV order; inspect each terminal result and physical backup ID.
- [ ] Confirm the backup verification record for the installed mechanism using [backup verification](../docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md).
- [ ] Enable the sole recurring schedule on VM 250:

```sh
sudo systemctl enable --now liora-backup.timer
systemctl list-timers liora-backup.timer --no-pager
systemctl is-active liora-backup-metrics.service
```

**Schedule:** Daily at 02:00 UTC. No VM 200 schedule and no independent Kubernetes ScheduledBackup.

## 3. Daily checks and manual full backups

- [ ] On VM 250, inspect service, timer and coordinator:

```sh
systemctl show liora-backup.service -p ActiveState -p SubState -p Result
systemctl list-timers liora-backup.timer --no-pager
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
```

- [ ] Require a finished cycle, empty holder and terminal results for all environments. A successful coordinator exit can include a definitively failed backup; inspect every step.
- [ ] Inspect Backup resources from the management host:

```sh
kubectl --kubeconfig="$HOME/.kube/config-prod" -n app-prod get backups.postgresql.cnpg.io
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-stage get backups.postgresql.cnpg.io
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-dev get backups.postgresql.cnpg.io
```

- [ ] Require current successful base backups, healthy continuous archiving and current telemetry.
- [ ] For a manual full cycle, use `coordinator.py run` under the same identity and global fence. Do not create parallel per-environment schedules.

The oneshot service is normally `inactive/dead` between cycles. A local lock,
durable Lease, owner-session fence and deterministic Backup names prevent
scheduled/manual overlap. Do not remove locks or clear the Lease to start work.

## 4. Recover a failed or interrupted cycle

- [ ] On VM 250, record the timer's enabled/active state and inspect diagnostics:

```sh
systemctl is-enabled liora-backup.timer
systemctl is-active liora-backup.timer
systemctl show liora-backup.service -p ActiveState -p SubState -p Result -p ExecMainStartTimestamp -p ExecMainExitTimestamp
sudo journalctl -u liora-backup.service --since '24 hours ago' --no-pager
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
sudo systemctl stop liora-backup.timer
```

- [ ] Confirm whether a process still owns the cycle. A lock/active-owner refusal means stop and inspect; do not launch another owner.
- [ ] Inspect the exact retained Backup objects, CNPG state, node resources, plugin logs and API connectivity.
- [ ] Correct the underlying failure before resuming. Compare node allocatable memory with VM configuration and guest memory when admission/resource errors occur.
- [ ] Resume the existing cycle, retaining its ID and Backup names:

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py resume
```

- [ ] Wait for completion and inspect all environment results. A failed backup is terminal and is not automatically retried; the coordinator proceeds to the next environment.
- [ ] If state is running or unknown, keep scheduling stopped and preserve the Lease, local journal and Kubernetes diagnostics.
- [ ] After terminal completion and an empty holder, clear the stale service failure:

```sh
sudo systemctl reset-failed liora-backup.service
```

- [ ] Restart `liora-backup.timer` only if it was active before maintenance; retain an intentionally disabled timer state.
- [ ] Recheck the next 02:00 UTC invocation, metrics and alert recovery.

**Stop:** Never edit Backup phases, delete the Lease/lock, remove database files or start a fresh cycle to conceal an unresolved previous attempt. After an interrupted SSH session, inspect the process before another resume.

## 5. Monitor and respond

- [ ] Apply each cluster's backup-monitoring resources after Prometheus CRDs exist:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply --server-side --field-manager=liora-backup-monitoring -k kubernetes/platform/nonprod/backup-monitoring
kubectl --kubeconfig="$HOME/.kube/config-prod" apply --server-side --field-manager=liora-backup-monitoring -k kubernetes/platform/prod/backup-monitoring
```

- [ ] Check VM 250 metrics on private TCP/9899 at `/metrics/nonprod` and `/metrics/prod`.
- [ ] Preserve ServiceMonitor `honorLabels: true` so source environment namespaces remain selectable.
- [ ] Match direct coordinator alert labels to native Prometheus identity, cluster, namespace and environment.
- [ ] Investigate failure, overdue backup, WAL error/backlog, missing telemetry, blocked-cycle and storage-usage alerts using [alert operations](../docs/operations/SLACK_ALERTING.md).
- [ ] Keep recovery notifications enabled; do not send daily success messages.
- [ ] At aggregate R2 usage above 10 GiB, review growth and capacity. The threshold is informational, not a quota or authorization to stop backups/delete data.

Usage enumeration covers every object page. A failed/partial scan is missing or
stale telemetry, not a valid smaller total. The full-backup freshness margin is
26 hours; WAL RPO is a separate objective.

**Done when:** Base backups and WAL are healthy, scheduling is serialized, telemetry is current, and backup verification records are retained.

## Related procedures

- [Live disaster recovery](../01-Disaster_recovery.md): rebuild and restore application data.
- [Backup verification](../docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md): monthly isolated PITR, WAL delivery measurements and guarded cleanup.
