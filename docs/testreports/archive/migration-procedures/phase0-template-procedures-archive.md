# Historical procedure record — 03-create-debian13-template

Archived on 2026-10-24 before the operational-manual rewrite. This preserves
one-time decisions, commands, observations and original limitations. Statements
about current status describe their original checkpoint. Do not use this record
as the installation or incident-response entrypoint. Operator scripts remain
in their original locations.

Current procedure: [03-create-debian13-template.md](../../../../runbooks/03-create-debian13-template.md).

---

# Create Debian 13 template VM 9013

**Where:** Proxmox VE 9 host. **Script:** `scripts/proxmox/create-debian13-template.sh`.

## Check VM ID 9013

- [ ] Complete [the private VNet](../../../../runbooks/01-create-private-vnet.md).
- [ ] Run `qm status 9013` and `qm config 9013` to check whether the ID is already in use.

### If template 9013 already exists

> [!NOTE]
> The script exits without changes. Inspect the existing template with `qm config 9013` before continuing.

```sh
# bash create-debian13-template.sh
Template 9013 already exists. No changes made. Verify its Debian 13 image and storage with: qm config 9013
```

### If ID 9013 belongs to a regular VM

> [!WARNING]
> The script stops without modifying the VM. Resolve the ID conflict before creating the template.

## Select VM disk storage

- [ ] On Proxmox, run `pvesm status` and `pvesm status --content images`. Check VM-image support and free space.
- [ ] With ID 9013 free, run `bash scripts/proxmox/create-debian13-template.sh` without `DISK_STORAGE`. It lists configured storages and does not create a VM. Confirm write permission before selecting a storage; a read-only listing cannot prove allocation permission.

### If `DISK_STORAGE` is unset

> [!NOTE]
> The script lists available storage and marks inactive, inaccessible, undersized, or non-image storage as unusable. This output was recorded on the current Proxmox host:

```sh
# bash create-debian13-template.sh
DISK_STORAGE is required. Inspect the options below, then rerun with DISK_STORAGE=<storage-id>.
Configured storage (required VM disk: 32 GiB):
Storage                Type         Status       Free             VM disk use
vmdata                 zfspool      active       5225.2 GiB       eligible (verify write permission)
local                  dir          active       27.9 GiB         cannot use: VM images not enabled
```

- [ ] Record the selected ID as `DISK_STORAGE` in the Git-ignored `recovery/.env` on your PC/laptop **before creating the template**. Keep `export TF_VAR_cloud_init_datastore_id="$DISK_STORAGE"` there for Terraform on VM 200. The current Scaleway host uses `vmdata`; `local` is small and `local-lvm` is absent. On a replacement host, use its own storage preflight.

## Create and verify the template

- [ ] With ID 9013 free, run `DISK_STORAGE=vmdata bash scripts/proxmox/create-debian13-template.sh` on the current host. On another host, replace `vmdata` with the ID recorded in `recovery/.env`. The script creates a 32 GiB disk by default.
- [ ] Check `qm config 9013` for the template flag, Debian cloud disk, Cloud-Init drive, and NIC on `vnet77`. Keep administrator private keys out of the template; supply each clone's SSH **public** key through Cloud-Init.

**Done when:** VM 9013 is a usable Debian 13 Cloud-Init template on the selected VM storage and `vnet77`. This step does not create a running management VM.
