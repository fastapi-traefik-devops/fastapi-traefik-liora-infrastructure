#!/usr/bin/env bash
set -euo pipefail

# Run on the Proxmox host as root.
#
# Change these values if your Proxmox environment differs.
TEMPLATE_ID="${TEMPLATE_ID:-9000}"
TEMPLATE_NAME="${TEMPLATE_NAME:-debian-13-cloud}"
BRIDGE="${BRIDGE:-vnet77}"
DISK_STORAGE="${DISK_STORAGE:-local-lvm}"
IMAGE_DIR="${IMAGE_DIR:-/var/lib/vz/template/iso}"
IMAGE_URL="${IMAGE_URL:-https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2}"
IMAGE_FILE="${IMAGE_FILE:-${IMAGE_DIR}/debian-13-generic-amd64.qcow2}"
DISK_SIZE_GB="${DISK_SIZE_GB:-32}"

if qm status "$TEMPLATE_ID" >/dev/null 2>&1; then
  echo "VM/template ID ${TEMPLATE_ID} already exists. Refusing to overwrite."
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
