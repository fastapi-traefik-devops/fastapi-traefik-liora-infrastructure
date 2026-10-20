# Provision the two K3s VM groups

**Where:** Run Terraform on management VM 200 from the repository root. Use
Proxmox to inspect existing VMs and storage.

## VM layout

| Cluster | VM IDs | VM names | Static IPs |
| --- | --- | --- | --- |
| dev/stage | 201, 202, 203 | `k3s-1-01`–`k3s-1-03` | `192.168.77.201`–`203` |
| prod | 211, 212, 213 | `k3s-2-01`–`k3s-2-03` | `192.168.77.211`–`213` |

## Preflight

- [ ] Confirm template `9013`, `vnet77`, gateway `192.168.77.1`, and VM disk storage from [the template runbook](03-create-debian13-template.md).
- [ ] Check that `recovery/.env` contains the current Proxmox API endpoint, node, token, and `DISK_STORAGE`. Confirm that `recovery/LIORA-id_ed25519.pub` is the intended public key for every node.
- [ ] Check any local `infrastructure/k3s-cluster/terraform/terraform.tfvars` overrides. Set `memory_mb = 8192` (maximum) and `memory_min_mb = 2048` (minimum) if those values are present; local values override the defaults.
- [ ] Inspect VMs `201`–`203` and `211`–`213` in Proxmox before planning. VM `200` is reserved for management and is not part of either cluster.

## Initialize Terraform and reconcile state

- [ ] Load the shared inputs, initialize the module, and validate it. Terraform is the default; use `tofu` consistently if you installed OpenTofu.

   ```sh
   source recovery/.env
   cd infrastructure/k3s-cluster/terraform
   terraform init
   terraform fmt -check
   terraform validate
   terraform state list
   ```

### If a VM already exists outside Terraform state

> [!WARNING]
> Import each existing VM **before** planning an apply. Run only the commands for VMs present in Proxmox but absent from `terraform state list`. Keep the existing state file; do not start with an empty state to work around a conflict.

- [ ] Import only the VMs that meet that condition:

```sh
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-01"]' "$TF_VAR_pm_node/201"
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-02"]' "$TF_VAR_pm_node/202"
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-03"]' "$TF_VAR_pm_node/203"
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-01"]' "$TF_VAR_pm_node/211"
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-02"]' "$TF_VAR_pm_node/212"
terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-03"]' "$TF_VAR_pm_node/213"
```

The provider's [VM import format](https://github.com/bpg/terraform-provider-proxmox/blob/v0.111.1/docs/resources/virtual_environment_vm.md#import) requires `node_name/vm_id`. Import records an existing VM in state without changing its guest configuration. A later plan may still propose changes to manually created VMs.

## Review and apply the plan

- [ ] Create and inspect the plan. On an empty host and state it should propose **six additions** with IDs `201`–`203` and `211`–`213`, template `9013`, bridge `vnet77`, selected Cloud-Init storage, matching static IPs, `root-admin`, the recovery public key, and ballooned memory with a 2 GiB minimum and 8 GiB maximum. Inspect every update or replacement of imported VMs.

   ```sh
   terraform plan -out=k3s.tfplan
   terraform show k3s.tfplan
   ```

### If the plan would replace a running cluster VM

> [!WARNING]
> Stop and reconcile state before applying an unexpected destruction or replacement.

- [ ] Apply the reviewed plan. Use `-parallelism=1` on this host to run VM operations sequentially. The first create keeps QEMU guest agent waiting disabled; Ansible installs it later.

   ```sh
   terraform apply -parallelism=1 k3s.tfplan
   ```

### If the host can handle concurrent clones

> [!NOTE]
> A full apply without `-parallelism=1` uses Terraform's default concurrency. Use this command **instead of** the sequential apply, only after reviewing the same saved plan.

```sh
terraform apply k3s.tfplan
```

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

## Check the result

- [ ] Verify the result in Proxmox and from VM 200:

```sh
terraform output k3s_nodes
ansible-inventory -i ../ansible/inventory-dev-stage.yml --graph
ansible-inventory -i ../ansible/inventory-prod.yml --graph
terraform plan
```

- [ ] Confirm all six VMs are running with the planned IDs, names, IPs, VNet, Cloud-Init key, and storage. Continue to [K3s installation](09-install-k3s-clusters.md), where Ansible checks SSH access.
