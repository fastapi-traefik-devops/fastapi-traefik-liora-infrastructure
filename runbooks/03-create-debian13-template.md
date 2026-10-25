# Create Debian 13 template VM 9013

**Where:** Start in the infrastructure checkout on the trusted laptop.
Copy `scripts/proxmox/create-debian13-template.sh` to the Proxmox VE 9 host.
Run the copied script there as root. The host does not need a Git checkout.

## Transfer the script

- [ ] From the repository checkout on your PC/laptop, copy the script to the
      current Proxmox host. Set `PROXMOX_PUBLIC_IP` to this host's address:

   ```sh
   read -r -p 'Current Proxmox public IPv4: ' PROXMOX_PUBLIC_IP
   scp scripts/proxmox/create-debian13-template.sh \
     root@"$PROXMOX_PUBLIC_IP":/root/create-debian13-template.sh
   ```

   Use the provider's root SSH access. If it requires a separate SSH key,
   add `-i /path/to/provider-key` to `scp`.

Continue on the Proxmox host as root. `/root/create-debian13-template.sh`
is the copied repository script. VM 200 and its `root-admin` home do not
exist yet.

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
- [ ] With ID 9013 free, run `bash /root/create-debian13-template.sh` without `DISK_STORAGE`. It lists configured storages and does not create a VM. Confirm write permission before selecting a storage; a read-only listing cannot prove allocation permission.

### If `DISK_STORAGE` is unset

> [!NOTE]
> Inspect the script's storage listing for active image-capable storage, free capacity and allocation permissions.

Example from the current host:

```sh
# bash /root/create-debian13-template.sh
DISK_STORAGE is required. Inspect the options below, then rerun with DISK_STORAGE=<storage-id>.
Configured storage (required VM disk: 32 GiB):
Storage                Type         Status       Free             VM disk use
vmdata                 zfspool      active       5225.2 GiB       eligible (verify write permission)
local                  dir          active       27.9 GiB         cannot use: VM images not enabled
```

- [ ] In a laptop terminal, edit the ignored `recovery/.env`. Set
      `DISK_STORAGE` to the selected ID. Keep
      `TF_VAR_cloud_init_datastore_id="$DISK_STORAGE"`. This gives the
      template script and Terraform the same storage ID. The current host
      uses `vmdata`; use the replacement host's own storage listing during
      recovery.

## Create and verify the template

- [ ] With ID 9013 free, enter the selected storage ID and run the copied
      repository script. The current host uses `vmdata`; another host may use
      a different ID from its storage preflight:

   ```sh
   read -r -p 'Selected VM disk storage ID: ' selected_storage
   DISK_STORAGE="$selected_storage" bash /root/create-debian13-template.sh
   ```

   The script creates a 32 GiB disk by default. The ID in
   `recovery/.env` on the laptop must match `selected_storage`.
- [ ] Check `qm config 9013` for the template flag, Debian cloud disk, Cloud-Init drive, and NIC on `vnet77`. Keep administrator private keys out of the template; supply each clone's SSH **public** key through Cloud-Init.

**Done when:** VM 9013 is a usable Debian 13 Cloud-Init template on the selected VM storage and `vnet77`. This step does not create a running management VM.
