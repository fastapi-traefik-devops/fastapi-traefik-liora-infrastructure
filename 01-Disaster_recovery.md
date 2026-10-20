# 01 — Infrastructure disaster recovery from scratch

Starting point: a replacement provider-supplied bare-metal server with preconfigured Proxmox, root access through SSH or the provider console, and one current public IPv4 address. Work from a trusted personal PC/laptop with an SSH client. Have the encrypted credential archive and its separately stored archive password, the existing administrator SSH key, verified backups, Terraform state, and the intended repository revision available. Expect the public IP to change; record the new value once as an input.

**Steps 1–6 are initiated from your own PC/laptop.** Use it to connect to and administer the replacement Proxmox host; VM 200 does not exist yet at the start of this phase.

1. **Identify recovery inputs.** Locate the existing SSH keys, backups, repository revision, and infrastructure state before provisioning. Preserve the originals. [Prepare recovery inputs](runbooks/10-prepare-recovery-inputs.md).
2. **Confirm the Proxmox baseline.** Require Proxmox VE 9; upgrade an 8.x host before continuing. Use nftables for custom host NAT rules. [Check Proxmox 9](runbooks/00-check-proxmox-9.md).
3. **Recreate the private network.** Restore `vnet77`, `192.168.77.0/24`, gateway `192.168.77.1`, and outbound SNAT. [Create the private VNet](runbooks/01-create-private-vnet.md).
4. **Reuse the administrator SSH key.** Prepare the existing public key for Cloud-Init; keep its private key in the local, Git-ignored `recovery/` directory. [Prepare SSH identity](runbooks/02-prepare-ssh-identity.md).
5. **Recreate the Debian 13 template.** Use template ID **9013**, preserving the ID used by the existing environment. [Create template 9013](runbooks/03-create-debian13-template.md).
6. **Recreate VM 200 and its SSH entry point.** Clone template 9013 at `192.168.77.200/24`, then forward public TCP port **22200** to its port 22 on the replacement host. Reconcile the bootstrapped VM with recovered state before any Terraform apply. [Create management VM 200](runbooks/04-create-management-vm-200.md) · [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

**Handoff after step 6:** All subsequent infrastructure recovery work runs on management VM 200. Use your PC/laptop as the SSH client; any check that must run elsewhere, such as VPN connectivity or public domain resolution, will be identified explicitly in its runbook.

7. **Move recovery to VM 200.** Connect with the existing key, obtain the verified repository revision, and prepare infrastructure state there. [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md) · [Install management tools](runbooks/11-install-management-tools.md) · [Prepare Proxmox API access](runbooks/12-create-proxmox-api-token.md).
8. **Restore private VPN access.** Recover or provision VM 250 and reestablish the Tailscale route to the private network. [Tailscale access stage](runbooks/07-tailscale-private-access.md).
9. **Recreate the two Kubernetes clusters.** Reconcile state before provisioning dev/stage **201–203** and prod **211–213**; then restore K3s and its required cluster identity. [Cluster VM provisioning](runbooks/08-provision-cluster-vms.md) · [K3s installation](runbooks/09-install-k3s-clusters.md).

Application and persistent-data restoration will be added as separate runbooks after this foundation is verified. Do not initialize replacement data where a verified backup must be restored.
