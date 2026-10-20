# 00 — New project installation from scratch

Starting point: a provider-supplied bare-metal server with preconfigured Proxmox, root access through SSH or the provider console, and one current public IPv4 address. Have a trusted personal PC/laptop with an SSH client and access to this repository. Prepare an encrypted credential archive (or a secure place to create one for this new project) and keep its archive password separately. Each link below leads to one local runbook.

**Steps 1–6 are initiated from your own PC/laptop.** Use it to connect to and administer the Proxmox host; VM 200 does not exist yet at the start of this phase.

1. **Confirm the Proxmox baseline.** Require Proxmox VE 9; upgrade an 8.x host before continuing. Use nftables for custom host NAT rules. [Check Proxmox 9](runbooks/00-check-proxmox-9.md).
2. **Create the private network.** Configure the `vnet77` VM network, `192.168.77.0/24`, gateway `192.168.77.1`, and outbound SNAT. [Create the private VNet](runbooks/01-create-private-vnet.md).
3. **Prepare an administrator SSH key.** Generate a new key pair on a trusted client; keep its private key in the local, Git-ignored `recovery/` directory. [Prepare SSH identity](runbooks/02-prepare-ssh-identity.md).
4. **Create the Debian 13 template.** Use template ID **9013**. The script defaults to `9013`; inspect VM disk storage before setting `DISK_STORAGE` and running it. [Create template 9013](runbooks/03-create-debian13-template.md).
5. **Create the management VM.** Clone template 9013 to **VM 200** at `192.168.77.200/24` and inject the public key through Cloud-Init. [Create management VM 200](runbooks/04-create-management-vm-200.md).
6. **Enable initial SSH access.** Forward public TCP port **22200** to `192.168.77.200:22` with persistent nftables DNAT. [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

**Handoff after step 6:** All subsequent infrastructure work runs on management VM 200. Use your PC/laptop as the SSH client; any check that must run elsewhere, such as VPN connectivity or public domain resolution, will be identified explicitly in its runbook.

7. **Move work to VM 200.** Connect over SSH, clone this repository, and continue infrastructure work there. [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md) · [Install management tools](runbooks/11-install-management-tools.md) · [Prepare Proxmox API access](runbooks/12-create-proxmox-api-token.md).
8. **Provide private VPN access.** Provision VM 250 and advertise the private subnet after the management path works. [Tailscale access stage](runbooks/07-tailscale-private-access.md).
9. **Build the two Kubernetes clusters.** Prepare dev/stage VMs **201–203** and prod VMs **211–213**, then install K3s. [Cluster VM provisioning](runbooks/08-provision-cluster-vms.md) · [K3s installation](runbooks/09-install-k3s-clusters.md).
