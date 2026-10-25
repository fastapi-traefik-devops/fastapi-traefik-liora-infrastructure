# Rebuild backup coordinator access

**Where:** Management VM 200, `~/fastapi-traefik-liora-infrastructure`.
**Use for:** New Kubernetes API identities after either cluster is rebuilt. This
procedure does not create a database or start a backup cycle.

## 1. Preserve the old profile

- [ ] Confirm the two kubeconfigs select the replacement clusters. Complete
      [CNPG and Barman operator installation](19-cnpg-r2-backup-pitr.md#install-platform-operators-in-either-scenario)
      and create the `app-dev`, `app-stage` and `app-prod` namespaces. Do not run
      the fresh-database section of runbook 19 during recovery.
- [ ] Confirm `recovery/recovery.yaml` contains the selected bucket credentials.
      Stop if an existing `r2-backup` Secret differs; `provision.py` refuses to
      rotate it automatically.
- [ ] Preserve an existing coordinator profile before generating a replacement:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
umask 077
profile=recovery/backup-coordinator.json
if test -e "$profile"; then
  saved="recovery/backup-coordinator.before-$(date -u +%Y%m%dT%H%M%SZ).json"
  test ! -e "$saved" || { echo 'Choose a new backup name' >&2; exit 1; }
  mv -- "$profile" "$saved"
  chmod 600 "$saved"
  printf 'Preserved previous profile: %s\n' "$saved"
fi
```

Keep the previous file in the encrypted recovery kit. If provisioning fails,
retain it and inspect the partial Kubernetes state; do not copy it back as the
new cluster profile.

## 2. Provision new cluster-bound access

- [ ] On VM 200, run the existing provisioner once:

```sh
bash scripts/local-python.sh scripts/backups/provision.py
test -s recovery/backup-coordinator.json
stat -c '%a %n' recovery/backup-coordinator.json
RECOVERY_PYTHON="$PWD/.local-work/venv/bin/python" bash recovery/check_credentials.sh --all --offline
bash scripts/local-python.sh scripts/backups/verify-coordinator-access.py
```

The provisioner applies `infrastructure/backup-coordinator/rbac-nonprod.yaml`
and `rbac-prod.yaml`, waits for each `backup-coordinator-token` Secret in
`cnpg-system`, reads its token and CA, and writes the two API endpoints to a
mode-0600 profile. It creates missing namespace `r2-backup` Secrets and refuses
conflicting ones. The read-only access check lists Backup resources in all
three namespaces and reads the PROD coordination Lease through the generated
tokens and CA certificates. Empty Backup lists are valid: this check does
**not** initialize an empty database or create a Backup.

**Stop:** An existing `backup-coordinator.json` with different content causes
the provisioner to fail. Preserve it under a dated name as in section 1, review
the cluster identity and R2 inputs, then rerun. Do not delete an unknown
profile or overwrite it to bypass the mismatch.

## 3. Install the replacement on VM 250

- [ ] Before installing, preserve any existing VM 250 configuration and
      journal. On VM 250, run:

```sh
sudo systemctl is-enabled liora-backup.timer || true
sudo systemctl is-active liora-backup.timer || true
sudo systemctl stop liora-backup.timer
if sudo test -f /etc/liora-backups/config.json; then
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  sudo install -m 600 -o liora-backups -g liora-backups \
    /etc/liora-backups/config.json "/etc/liora-backups/config.before-$stamp.json"
fi
sudo ls -ld /var/lib/liora-backups
```

- [ ] Verify VM 250's host key and install the prepared profile using
      [runbook 19, section 2](19-cnpg-r2-backup-pitr.md#2-install-the-coordinator-on-vm-250).
      `install-vm250.sh` copies `recovery/backup-coordinator.json` to
      `/etc/liora-backups/config.json` as `liora-backups`, mode `0600`.
- [ ] After installation, on VM 250 run the read-only coordinator inspection:

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python \
  /opt/liora-backups/coordinator.py inspect
sudo systemctl is-active liora-backup-metrics.service
sudo systemctl is-enabled liora-backup.timer || true
```

**Expected:** Both API endpoints are reachable, the coordinator can inspect
its global fence, and metrics are active. Inspection is independent of database
initialization; do not run `coordinator.py run` until restored databases,
ObjectStores and WAL are ready. Keep the timer stopped until the recovery
navigator reviews its recorded prior state and releases scheduling.

**If interrupted:** Inspect the VM 250 timer, local cycle journal and global
Lease before any run or resume. Preserve both old profiles and the generated
replacement; never reset a live fence to force a cycle.
