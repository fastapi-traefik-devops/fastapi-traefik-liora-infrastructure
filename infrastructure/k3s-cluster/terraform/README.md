# Provision K3s cluster VMs with Terraform

Run Terraform on management VM 200. This module clones Debian 13 template
`9013` into six VMs on `vnet77`. It creates only VMs and Cloud-Init settings;
the [Ansible playbooks](../ansible/README.md) install K3s afterward.

## VM layout

| Cluster | VM IDs | VM names | Static IPs |
| --- | --- | --- | --- |
| dev/stage | 201–203 | `k3s-1-01`–`k3s-1-03` | `192.168.77.201`–`203` |
| prod | 211–213 | `k3s-2-01`–`k3s-2-03` | `192.168.77.211`–`213` |

## Inputs and state

The module uses the same `TF_VAR_pm_*` credentials, Proxmox node, and
`TF_VAR_cloud_init_datastore_id` from `recovery/.env` as the Tailscale module.
The SSH public key is `recovery/LIORA-id_ed25519.pub`. Keep the corresponding
private key local. The template's VM disk is cloned onto its existing storage;
`cloud_init_datastore_id` selects storage for the Cloud-Init drive.

Follow the [VM provisioning runbook](../../../runbooks/08-provision-cluster-vms.md)
for preflight checks, import instructions for VMs already created manually,
plan review, and verification. Terraform state is local to this directory and
must be preserved separately from the K3s cluster backups.
