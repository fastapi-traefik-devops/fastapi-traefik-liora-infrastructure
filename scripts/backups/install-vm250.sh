#!/usr/bin/env bash
# Install only this coordinator; never reconfigure Tailscale or enable the timer implicitly.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_dir"
identity="$repo_dir/recovery/LIORA-id_ed25519"
config="$repo_dir/recovery/backup-coordinator.json"
known="$repo_dir/.local-work/private/phase10-2/known_hosts"
remote_host=root-admin@192.168.77.250
ssh_args=(-i "$identity" -o BatchMode=yes -o ConnectTimeout=15 -o "UserKnownHostsFile=$known")
[[ -s "$config" && -s "$known" ]] || { echo 'Provision private credentials and verify the VM 250 host key first' >&2; exit 1; }
ssh "${ssh_args[@]}" "$remote_host" 'install -d -m 700 "$HOME/.liora-backup-install"; sudo -n systemctl is-active --quiet tailscaled'
scp "${ssh_args[@]}" scripts/backups/{coordinator.py,metrics.py,requirements.txt} infrastructure/backup-coordinator/liora-backup* "$config" "$remote_host:.liora-backup-install/"
ssh "${ssh_args[@]}" "$remote_host" 'bash -s' <<'REMOTE'
set -euo pipefail
stage="$HOME/.liora-backup-install"
if sudo test -d /opt/liora-backups && ! sudo test -f /opt/liora-backups/.liora-managed; then
  echo 'Existing unrecognized coordinator directory: preserve and inspect it' >&2; exit 1
fi
sudo -n apt-get update -qq
sudo -n apt-get install -y -qq python3-venv
id liora-backups >/dev/null 2>&1 || sudo -n useradd --system --home-dir /var/lib/liora-backups --shell /usr/sbin/nologin liora-backups
sudo -n install -d -m 755 /opt/liora-backups
sudo -n touch /opt/liora-backups/.liora-managed
sudo -n python3 -m venv /opt/liora-backups/venv
sudo -n /opt/liora-backups/venv/bin/python -m pip install --disable-pip-version-check -r "$stage/requirements.txt"
sudo -n install -m 644 "$stage/coordinator.py" "$stage/metrics.py" "$stage/requirements.txt" /opt/liora-backups/
sudo -n install -d -m 750 -o root -g liora-backups /etc/liora-backups
sudo -n install -m 600 -o liora-backups -g liora-backups "$stage/backup-coordinator.json" /etc/liora-backups/config.json
sudo -n install -d -m 700 -o liora-backups -g liora-backups /var/lib/liora-backups
sudo -n install -m 644 "$stage/liora-backup.service" "$stage/liora-backup.timer" "$stage/liora-backup-metrics.service" /etc/systemd/system/
rm -f "$stage/backup-coordinator.json"
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now liora-backup-metrics.service
sudo -n systemctl is-active --quiet tailscaled
sudo -n sysctl net.ipv4.ip_forward
printf 'Coordinator installed; metrics enabled; daily timer awaits explicit acceptance activation.\n'
REMOTE
