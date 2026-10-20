#!/usr/bin/env bash
set -euo pipefail

# Run on the Proxmox host as root.
#
# Change these values if your Proxmox environment differs.
TEMPLATE_ID="${TEMPLATE_ID:-9013}"
TEMPLATE_NAME="${TEMPLATE_NAME:-debian-13-cloud}"
BRIDGE="${BRIDGE:-vnet77}"
DISK_STORAGE="${DISK_STORAGE:-}"
IMAGE_DIR="${IMAGE_DIR:-/var/lib/vz/template/iso}"
IMAGE_URL="${IMAGE_URL:-https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2}"
IMAGE_FILE="${IMAGE_FILE:-${IMAGE_DIR}/debian-13-generic-amd64.qcow2}"
DISK_SIZE_GB="${DISK_SIZE_GB:-32}"

if (( EUID != 0 )); then
  echo "Run this script as root on the Proxmox host." >&2
  exit 1
fi

for command_name in qm pvesm; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required Proxmox command: ${command_name}" >&2
    exit 1
  fi
done

if qm status "$TEMPLATE_ID" >/dev/null 2>&1; then
  if qm config "$TEMPLATE_ID" | grep -Eq '^template:[[:space:]]*1([[:space:]]|$)'; then
    echo "Template ${TEMPLATE_ID} already exists. No changes made. Verify its Debian 13 image and storage with: qm config ${TEMPLATE_ID}"
    exit 0
  fi
  echo "ID ${TEMPLATE_ID} is occupied by a VM that is not a template. No changes made." >&2
  exit 1
fi

if ! [[ "$DISK_SIZE_GB" =~ ^[1-9][0-9]*$ ]]; then
  echo "DISK_SIZE_GB must be a positive integer." >&2
  exit 1
fi

SELECTED_STORAGE_OK=0

show_storage_options() {
  local all_status image_status storage_id row type state available free_gib reason
  local -a storage_ids

  if [[ ! -r /etc/pve/storage.cfg ]]; then
    echo "Cannot read /etc/pve/storage.cfg to list all configured storages." >&2
    return 1
  fi
  mapfile -t storage_ids < <(awk '/^[^[:space:]#][^:]*:[[:space:]]+/ {print $2}' /etc/pve/storage.cfg)
  if ((${#storage_ids[@]} == 0)); then
    echo "No configured Proxmox storages were found." >&2
    return 1
  fi
  if ! all_status="$(pvesm status)"; then
    echo "Cannot read Proxmox storage status." >&2
    return 1
  fi
  if ! image_status="$(pvesm status --content images)"; then
    echo "Cannot determine which storages support VM images." >&2
    return 1
  fi

  printf 'Configured storage (required VM disk: %s GiB):\n' "$DISK_SIZE_GB"
  printf '%-22s %-12s %-12s %-16s %s\n' 'Storage' 'Type' 'Status' 'Free' 'VM disk use'
  for storage_id in "${storage_ids[@]}"; do
    row="$(awk -v id="$storage_id" 'NR > 1 && $1 == id {print $2, $3, $6}' <<<"$all_status")"
    if [[ -z "$row" ]]; then
      type='unknown'
      state='unavailable'
      free_gib='unknown'
      reason='cannot use: no status or access'
    else
      read -r type state available <<<"$row"
      if [[ "$available" =~ ^[0-9]+$ ]]; then
        free_gib="$(awk -v kib="$available" 'BEGIN {printf "%.1f GiB", kib / 1048576}')"
      else
        free_gib='unknown'
      fi
      if ! awk -v id="$storage_id" 'NR > 1 && $1 == id {found=1} END {exit !found}' <<<"$image_status"; then
        reason='cannot use: VM images not enabled'
      elif [[ "$state" != active ]]; then
        reason='cannot use: inactive or disabled'
      elif ! pvesm list "$storage_id" --content images >/dev/null 2>&1; then
        reason='cannot use: access check failed'
      elif [[ ! "$available" =~ ^[0-9]+$ ]] || (( available < DISK_SIZE_GB * 1048576 )); then
        reason='cannot use: insufficient free space'
      else
        reason='eligible (verify write permission)'
        if [[ "$storage_id" == "$DISK_STORAGE" ]]; then
          SELECTED_STORAGE_OK=1
        fi
      fi
    fi
    printf '%-22s %-12s %-12s %-16s %s\n' "$storage_id" "$type" "$state" "$free_gib" "$reason"
  done
}

if [[ -z "$DISK_STORAGE" ]]; then
  echo "DISK_STORAGE is required. Inspect the options below, then rerun with DISK_STORAGE=<storage-id>." >&2
  show_storage_options
  exit 2
fi

show_storage_options
if (( ! SELECTED_STORAGE_OK )); then
  echo "DISK_STORAGE=${DISK_STORAGE} is not an eligible VM disk storage. No changes made." >&2
  exit 1
fi

mkdir -p "$IMAGE_DIR"

echo "[1/8] Download Debian 13 cloud image"
curl -fL --retry 3 -o "$IMAGE_FILE" "$IMAGE_URL"

echo "[2/8] Create VM shell"
qm create "$TEMPLATE_ID" \
  --name "$TEMPLATE_NAME" \
  --memory 2048 \
  --cores 2 \
  --cpu x86-64-v2-AES \
  --net0 "virtio,bridge=${BRIDGE}" \
  --ostype l26

echo "[3/8] Import cloud disk"
qm importdisk "$TEMPLATE_ID" "$IMAGE_FILE" "$DISK_STORAGE"

# Proxmox names the first imported disk vm-<id>-disk-0 on normal storages.
echo "[4/8] Attach imported disk"
qm set "$TEMPLATE_ID" \
  --scsihw virtio-scsi-single \
  --scsi0 "${DISK_STORAGE}:vm-${TEMPLATE_ID}-disk-0,discard=on,iothread=1"

echo "[5/8] Resize template disk"
qm resize "$TEMPLATE_ID" scsi0 "${DISK_SIZE_GB}G"

echo "[6/8] Add Cloud-Init disk and serial console"
qm set "$TEMPLATE_ID" --ide2 "${DISK_STORAGE}:cloudinit"
qm set "$TEMPLATE_ID" --boot order=scsi0
qm set "$TEMPLATE_ID" --serial0 socket --vga serial0

echo "[7/8] Enable QEMU agent device"
# The guest package itself is installed later by node preparation.
qm set "$TEMPLATE_ID" --agent enabled=1

echo "[8/8] Convert to template"
qm template "$TEMPLATE_ID"

echo
echo "Created template:"
echo "  ID:      ${TEMPLATE_ID}"
echo "  Name:    ${TEMPLATE_NAME}"
echo "  Bridge:  ${BRIDGE}"
echo "  Storage: ${DISK_STORAGE}"
echo
echo "Next: clone it manually or use infrastructure/opentofu."
