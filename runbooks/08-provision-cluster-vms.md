# Provision the two K3s VM groups

**Where:** Run Terraform on management VM 200 from the repository root. Use
Proxmox to inspect existing VMs and storage.

## VM layout

| Cluster | VM IDs | VM names | Static IPs |
| --- | --- | --- | --- |
| dev/stage | 201, 202, 203 | `k3s-1-01`–`k3s-1-03` | `192.168.77.201`–`203` |
| prod | 211, 212, 213 | `k3s-2-01`–`k3s-2-03` | `192.168.77.211`–`213` |

## Preflight

1. Confirm template `9013`, `vnet77`, gateway `192.168.77.1`, and the selected
   VM disk storage from [the template runbook](03-create-debian13-template.md).
   Check that `recovery/.env` contains the current Proxmox API endpoint, node,
   token, and `DISK_STORAGE`. Confirm that
   `recovery/LIORA-id_ed25519.pub` is the public key intended for every node.
   Inspect VMs `201`–`203` and `211`–`213` in Proxmox before planning. VM `200`
   is reserved for management and is not part of either cluster.

## Initialize Terraform and reconcile state

1. Load the shared inputs, initialize the module, and validate it. Terraform
   is the default; replace `terraform` with `tofu` consistently if using
   OpenTofu.

   ```sh
   source recovery/.env
   cd infrastructure/k3s-cluster/terraform
   terraform init
   terraform fmt -check
   terraform validate
   terraform state list
   ```

2. If these six VMs **already exist** from manual provisioning but are absent
   from this module's state, import each existing VM **before** planning an
   apply. Run only the import commands for VMs that exist and are not already
   in `terraform state list`. Keep the existing state file; do not start with
   a fresh state to work around a conflict.

   ```sh
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-01"]' "$TF_VAR_pm_node/201"
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-02"]' "$TF_VAR_pm_node/202"
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-1-03"]' "$TF_VAR_pm_node/203"
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-01"]' "$TF_VAR_pm_node/211"
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-02"]' "$TF_VAR_pm_node/212"
   terraform import 'proxmox_virtual_environment_vm.k3s["k3s-2-03"]' "$TF_VAR_pm_node/213"
   ```

   The provider's [VM import format](https://github.com/bpg/terraform-provider-proxmox/blob/v0.111.1/docs/resources/virtual_environment_vm.md#import)
   requires `node_name/vm_id`. Import records the existing VMs in Terraform
   state; it does not rename them or change their guest configuration. A
   following plan can still propose changes because manually created VMs may
   differ from the module.

## Review and apply the plan

1. Review the plan. On an empty Proxmox host with an empty state, it should
   propose **six additions** with IDs `201`–`203` and `211`–`213`, template
   `9013`, bridge `vnet77`, the selected Cloud-Init drive storage, matching
   static IPs, `root-admin`, and the recovery public key. For imported VMs,
   inspect every proposed update or replacement. Stop if Terraform proposes
   to destroy or replace a running cluster VM unexpectedly.

   ```sh
   terraform plan -out=k3s.tfplan
   terraform show k3s.tfplan
   ```

2. Apply the reviewed plan. Prefer `-parallelism=1` on this host so Terraform
   runs VM operations sequentially. The full apply without this limit remains
   available on a host that can handle concurrent clones. The first create
   keeps QEMU guest agent waiting disabled; Ansible installs the agent later.

   ```sh
   terraform apply -parallelism=1 k3s.tfplan
   ```

   Full apply with Terraform's default parallelism:

   ```sh
   terraform apply k3s.tfplan
   ```

## Check the result

Verify the result in Proxmox and from VM 200:

```sh
terraform output k3s_nodes
ansible-inventory -i ../ansible/inventory-dev-stage.yml --graph
ansible-inventory -i ../ansible/inventory-prod.yml --graph
terraform plan
```

Confirm all six VMs are running with the planned IDs, names, IPs, VNet,
Cloud-Init key, and storage. Check SSH to all six VMs before continuing
with [the K3s installation runbook](09-install-k3s-clusters.md).

## Troubleshooting: storage lock and leftover clone volumes

On a host with limited storage throughput, several long-running clones can
hit a Proxmox `pve-storage-vmdata` lock timeout. A failed clone can leave its
Cloud-Init volume behind. The next attempt then reports that a dataset such
as `zpve/vm-202-cloudinit` already exists.

1. On VM 200, check `terraform state list` and `terraform plan`. Confirm which
   VM IDs are absent from state and still proposed for creation. On the
   Proxmox host, inspect those IDs and their volumes. For the verified case:

   ```sh
   qm config 202
   qm config 213
   pvesm list vmdata --vmid 202
   pvesm list vmdata --vmid 213
   ```

2. Only if both VM configuration files are absent and the listed volumes are
   the orphaned Cloud-Init volumes from the failed clones, free those exact
   volumes on the Proxmox host. `pvesm free` destroys the selected volume.
   Do not remove a volume referenced by an existing VM.

   ```sh
   pvesm free vmdata:vm-202-cloudinit
   pvesm free vmdata:vm-213-cloudinit
   ```

3. Back on VM 200, make a fresh plan after the partial apply. Prefer retrying
   with sequential VM operations only if the plan proposes the expected
   missing VMs and no unexpected changes or deletions:

   ```sh
   terraform plan
   terraform apply -parallelism=1
   ```

   If a separate apply for each missing VM is needed, target one at a time as
   in the verified recovery. Resource targeting is for this exceptional
   recovery case; always run a full plan afterward.

   ```sh
   terraform apply -target='proxmox_virtual_environment_vm.k3s["k3s-1-02"]'
   terraform apply -target='proxmox_virtual_environment_vm.k3s["k3s-2-03"]'
   terraform plan
   ```
