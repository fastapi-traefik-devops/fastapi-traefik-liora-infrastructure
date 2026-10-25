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
- [ ] Check the current Proxmox API endpoint, node, token, and
      `DISK_STORAGE` in `recovery/.env`.
- [ ] Confirm `recovery/LIORA-id_ed25519.pub` is the SSH public key for
      all six nodes.
- [ ] Check local `infrastructure/k3s-cluster/terraform/terraform.tfvars`.
      If it overrides memory, use `memory_mb = 8192` for the maximum and
      `memory_min_mb = 2048` for the minimum.
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
> Import each existing VM before you apply a plan. Run only the import
> commands for VMs that exist in Proxmox and are absent from
> `terraform state list`. Keep the existing state file.

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

- [ ] Create and inspect the plan. On an empty host and state, require six
      additions: VMs `201`–`203` and `211`–`213`.
- [ ] Check template `9013`, bridge `vnet77`, selected Cloud-Init storage,
      static IPs, user `root-admin`, and the recovery public key.
- [ ] Check ballooned memory: 2 GiB minimum and 8 GiB maximum.
      Inspect every update or replacement of an imported VM.

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

- [ ] Inspect the failed resource's VM ID, Terraform state and Proxmox storage inventory.
- [ ] Confirm whether VM creation completed before planning another apply; import a surviving VM when required.
- [ ] Identify any orphaned Cloud-Init volume by its exact storage/VM identity and prove no VM references it before an authorized removal.
- [ ] Create a new full plan after the partial apply. Retry sequentially only for the expected missing resources; stop on unrelated destruction/replacement.
- [ ] Do not reuse a stale plan or copy volume-deletion commands from another incident.

## Check the result

- [ ] Verify the result in Proxmox and from VM 200:

```sh
terraform output k3s_nodes
ansible-inventory -i ../ansible/inventory-dev-stage.yml --graph
ansible-inventory -i ../ansible/inventory-prod.yml --graph
terraform plan
```

- [ ] Confirm all six VMs are running with the planned IDs, names, IPs, VNet, Cloud-Init key, and storage. Continue to [K3s installation](09-install-k3s-clusters.md), where Ansible checks SSH access.
