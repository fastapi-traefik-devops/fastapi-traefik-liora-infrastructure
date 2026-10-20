# Provision the two K3s VM groups

**Where:** VM 200 for automation, Proxmox host for inspection. **Status:** Target inventory is established; the current Terraform code has not been tested for this layout and must not be applied unchanged.

| Environment | VM IDs | Static IPs |
| --- | --- | --- |
| dev/stage | 201, 202, 203 | 192.168.77.201–203 |
| prod | 211, 212, 213 | 192.168.77.211–213 |

1. Confirm template `9013`, `vnet77`, gateway `192.168.77.1`, free target IDs/IPs, and the public SSH key for Cloud-Init. VM `200` is reserved for management.
2. Inspect the current Proxmox inventory. During recovery, inspect and reconcile the restored Terraform state **before** planning any create or replacement action.
3. Adapt `infrastructure/terraform/` for two distinct VM groups and this table, then review `terraform plan`/`tofu plan`. The current `locals.tf` targets VM IDs `2200–2202` with `.200–.202`, while the template default is `9013`. The node IDs and IPs do **not** describe the target infrastructure.
4. The checked-in `scripts/proxmox/create-3-vms-for-k3s-cluster.sh` is a tested manual artifact, and now clones template `9013`, but it creates only VMs `201–203`. Do not use it as a complete two-cluster build or recovery procedure.
5. Apply only a reviewed plan, then verify each VM's ID, IP, VNet, Cloud-Init key, boot status, and SSH access. Record which resources are managed by Terraform state before installing K3s.

**Still needed:** Tested Terraform configuration for both groups. A plan is a review artifact, not proof that deployment or disaster recovery has succeeded.
