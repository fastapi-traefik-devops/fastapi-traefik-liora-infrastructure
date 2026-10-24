# Create Debian 13 template VM 9013

**Where:** Proxmox VE 9 host. **Script:** `scripts/proxmox/create-debian13-template.sh`.

## Check VM ID 9013

- [ ] Complete [the private VNet](01-create-private-vnet.md).
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
> Inspect the script's storage listing for active image-capable storage, free capacity and allocation permissions.

- [ ] Record the selected ID as `DISK_STORAGE` in the Git-ignored `recovery/.env` on your PC/laptop **before creating the template**. Keep `export TF_VAR_cloud_init_datastore_id="$DISK_STORAGE"` there for Terraform on VM 200. The current Scaleway host uses `vmdata`; `local` is small and `local-lvm` is absent. On a replacement host, use its own storage preflight.

## Create and verify the template

- [ ] With ID 9013 free, run `DISK_STORAGE=vmdata bash scripts/proxmox/create-debian13-template.sh` on the current host. On another host, replace `vmdata` with the ID recorded in `recovery/.env`. The script creates a 32 GiB disk by default.
- [ ] Check `qm config 9013` for the template flag, Debian cloud disk, Cloud-Init drive, and NIC on `vnet77`. Keep administrator private keys out of the template; supply each clone's SSH **public** key through Cloud-Init.

**Done when:** VM 9013 is a usable Debian 13 Cloud-Init template on the selected VM storage and `vnet77`. This step does not create a running management VM.
