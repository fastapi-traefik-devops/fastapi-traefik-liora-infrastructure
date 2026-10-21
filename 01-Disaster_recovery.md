# 01 — Infrastructure disaster recovery from scratch

## Before you start

- [ ] Obtain a replacement bare-metal server with Proxmox, root access through SSH or the provider console, and its **current** public IPv4 address.
- [ ] Prepare a trusted PC/laptop with an SSH client, the intended repository revision, and the encrypted credential archive with its separately stored password.
- [ ] Locate the existing administrator SSH key, Terraform state, and verified cluster and application backups. Preserve the originals.

The public IP can change during recovery. Record the replacement value as an input; use the private Proxmox API address from VM 200.

> [!IMPORTANT]
> This navigator rebuilds infrastructure through a fresh K3s bootstrap. Restoring an etcd snapshot or application data is a separate procedure. Preserve the matching backup and original K3s server token for each cluster.

## Steps 1–6 — Work from your PC/laptop

VM 200 does not exist yet. Use your PC/laptop to administer the replacement Proxmox host.

1. **Identify recovery inputs.** Match keys, backups, repository revision, and infrastructure state before provisioning.
   - [ ] [Prepare recovery inputs](runbooks/10-prepare-recovery-inputs.md).
2. **Confirm the Proxmox baseline.** Require Proxmox VE 9 and use nftables for custom host NAT rules.
   - [ ] [Check Proxmox 9](runbooks/00-check-proxmox-9.md).
3. **Recreate the private network.** Restore `vnet77`, `192.168.77.0/24`, gateway `192.168.77.1`, and outbound SNAT.
   - [ ] [Create the private VNet](runbooks/01-create-private-vnet.md).
4. **Reuse the administrator SSH key.** Restore the existing key pair; keep its private key in the local, Git-ignored `recovery/` directory.
   - [ ] [Prepare SSH identity](runbooks/02-prepare-ssh-identity.md).
5. **Recreate the Debian 13 template.** Use template ID **9013**.
   - [ ] [Create template 9013](runbooks/03-create-debian13-template.md).
6. **Recreate VM 200 and its SSH entry point.** Clone template 9013 at `192.168.77.200/24`, then forward public TCP port **22200** to its port 22. VM 200 is created directly on Proxmox and is not declared in Terraform.
   - [ ] [Create management VM 200](runbooks/04-create-management-vm-200.md).
   - [ ] [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

## Handoff after step 6 — Move to management VM 200

Run all subsequent infrastructure recovery commands on **VM 200**. Use your PC/laptop as the SSH client. A runbook explicitly identifies checks that must run elsewhere, such as VPN connectivity or public domain resolution.

7. **Prepare VM 200 as the control machine.** Connect with the existing key, obtain the intended repository revision, install tools, and prepare Proxmox API access.
   - [ ] [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md).
   - [ ] [Install Ansible and Terraform](runbooks/11-install-management-tools.md).
   - [ ] [Prepare Proxmox API access](runbooks/12-create-proxmox-api-token.md).
8. **Restore private VPN access.** Recover or provision VM 250 and reestablish the route to the private network.
   - [ ] [Provision Tailscale access](runbooks/07-tailscale-private-access.md).
9. **Recreate the two Kubernetes clusters.** Reconcile Terraform state, provision dev/stage VMs **201–203** and prod VMs **211–213**, then install K3s.
   - [ ] [Provision the cluster VMs](runbooks/08-provision-cluster-vms.md).
   - [ ] [Install K3s on both clusters](runbooks/09-install-k3s-clusters.md).
10. **Deploy and verify the application manifests.** Use the assigned cluster and isolated namespace for each environment; complete this step only when its deployment phase is authorized.
    - [ ] [Deploy the application manifests](runbooks/13-deploy-application-manifests.md).
