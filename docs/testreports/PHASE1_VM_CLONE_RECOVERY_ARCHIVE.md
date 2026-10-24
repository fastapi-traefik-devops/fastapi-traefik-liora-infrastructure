# Phase 1 — Historical VM clone recovery instructions

Archived 2026-10-24. The addresses/volume IDs below belong to the original
partial-apply incident. Use [the current procedure](../../runbooks/08-provision-cluster-vms.md)
for new operations; do not repeat those historical deletions on another host.

### If cloning fails with a storage lock or leftover volume

> [!WARNING]
> On a host with limited storage throughput, concurrent clones can hit a `pve-storage-vmdata` lock timeout. A failed clone may leave a Cloud-Init volume; a retry then reports a dataset such as `zpve/vm-202-cloudinit` already exists. Inspect Proxmox and Terraform state before removing anything.

- [ ] On VM 200, check `terraform state list` and `terraform plan`. Confirm which IDs are absent from state and still proposed for creation. On Proxmox, inspect only those IDs and volumes. For the verified case:

   ```sh
   qm config 202
   qm config 213
   pvesm list vmdata --vmid 202
   pvesm list vmdata --vmid 213
   ```

- [ ] Only when **both** VM configuration files are absent and the listed volumes are orphaned Cloud-Init volumes from those failed clones, free the exact volumes on Proxmox. `pvesm free` destroys the selected volume; never remove one referenced by an existing VM.

   ```sh
   pvesm free vmdata:vm-202-cloudinit
   pvesm free vmdata:vm-213-cloudinit
   ```

- [ ] On VM 200, make a fresh plan after the partial apply. Retry sequentially only if it proposes the expected missing VMs with no unexpected changes or deletions:

   ```sh
   terraform plan
   terraform apply -parallelism=1
   ```

#### If a separate retry for each missing VM is needed

> [!WARNING]
> Target one missing VM at a time only for this exceptional recovery case. Run a full plan afterward.

   ```sh
   terraform apply -target='proxmox_virtual_environment_vm.k3s["k3s-1-02"]'
   terraform apply -target='proxmox_virtual_environment_vm.k3s["k3s-2-03"]'
   terraform plan
   ```
