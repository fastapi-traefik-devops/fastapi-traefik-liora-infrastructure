# Create Debian 13 template VM 9013

**Where:** Proxmox VE 9 host. **Script:** `scripts/proxmox/create-debian13-template.sh`.

1. Complete [the private VNet](01-create-private-vnet.md). Check `qm status 9013` and `qm config 9013` to see whether the ID is already in use. An existing template is safe: the script reports it and exits without changes. If ID 9013 belongs to a regular VM, the script stops without modifying it.
2. On the Proxmox host, run `pvesm status` and `pvesm status --content images`. Check the free space and that the selected storage supports VM images. Run `bash scripts/proxmox/create-debian13-template.sh` without `DISK_STORAGE` to see the script's annotated list of all configured storages; it will not create a VM. Storages without VM-image support, active status, sufficient space, or accessible listing are marked unusable. Confirm write permission before selecting a storage; a read-only listing alone cannot prove allocation permission.
3. After selecting eligible storage, update `DISK_STORAGE` in the Git-ignored `recovery/.env` on your PC/laptop **before creating the template**. Keep `export TF_VAR_cloud_init_datastore_id="$DISK_STORAGE"` in that file; it passes the same storage ID to Terraform later on VM 200. On the current Scaleway host, set `DISK_STORAGE='vmdata'`. Its `local` storage is small and reserved for Proxmox, and `local-lvm` is absent. On a replacement host, use the ID shown by its own preflight. The template script creates a 32 GiB disk by default.
4. With ID 9013 free, run `DISK_STORAGE=vmdata bash scripts/proxmox/create-debian13-template.sh` on the current Proxmox host. On another host, replace `vmdata` with **the same ID recorded in `recovery/.env`**. The script downloads the Debian 13 cloud image and creates the template only after the storage preflight passes.
5. Verify `qm config 9013`: template flag, Debian cloud disk, Cloud-Init drive, and NIC on `vnet77`. Keep the template free of administrator private keys. Supply each clone's SSH **public** key through Cloud-Init.

## Observed preflight output

These outputs were recorded on the current Proxmox host in separate starting states. When template 9013 already exists, the script exits before the storage check:

```sh
# bash create-debian13-template.sh
Template 9013 already exists. No changes made. Verify its Debian 13 image and storage with: qm config 9013
```

When ID 9013 is free and `DISK_STORAGE` is unset, the script lists configured storages and exits without creating a VM:

```sh
# bash create-debian13-template.sh
DISK_STORAGE is required. Inspect the options below, then rerun with DISK_STORAGE=<storage-id>.
Configured storage (required VM disk: 32 GiB):
Storage                Type         Status       Free             VM disk use
vmdata                 zfspool      active       5225.2 GiB       eligible (verify write permission)
local                  dir          active       27.9 GiB         cannot use: VM images not enabled
```

**Done when:** VM 9013 is a usable Debian 13 Cloud-Init template on the selected VM storage and `vnet77`. This step does not create a running management VM.
