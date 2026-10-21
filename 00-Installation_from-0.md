# 00 — New project installation from scratch

## Before you start

- [ ] Obtain a provider-supplied bare-metal server with Proxmox, root access through SSH or the provider console, and its current public IPv4 address.
- [ ] Prepare a trusted PC/laptop with an SSH client and access to this repository.
- [ ] Prepare an encrypted credential archive or a secure place to create one. Keep its password separately.

Each checklist link opens one local runbook. Complete the linked actions in order.

## Steps 1–6 — Work from your PC/laptop

VM 200 does not exist yet. Use your PC/laptop to administer the Proxmox host.

1. **Confirm the Proxmox baseline.** Require Proxmox VE 9 and use nftables for custom host NAT rules.
   - [ ] [Check Proxmox 9](runbooks/00-check-proxmox-9.md).
2. **Create the private network.** Configure `vnet77`, `192.168.77.0/24`, gateway `192.168.77.1`, and outbound SNAT.
   - [ ] [Create the private VNet](runbooks/01-create-private-vnet.md).
3. **Prepare an administrator SSH key.** Generate a new pair on the trusted client; keep the private key in the local, Git-ignored `recovery/` directory.
   - [ ] [Prepare SSH identity](runbooks/02-prepare-ssh-identity.md).
4. **Create the Debian 13 template.** Use VM ID **9013** and select the host's VM disk storage before running the script.
   - [ ] [Create template 9013](runbooks/03-create-debian13-template.md).
5. **Create the management VM.** Clone template 9013 to **VM 200** at `192.168.77.200/24`; inject the public key through Cloud-Init.
   - [ ] [Create management VM 200](runbooks/04-create-management-vm-200.md).
6. **Enable initial SSH access.** Forward public TCP port **22200** to `192.168.77.200:22` with persistent nftables DNAT.
   - [ ] [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

## Handoff after step 6 — Move to management VM 200

Run all subsequent infrastructure commands on **VM 200**. Use your PC/laptop as the SSH client. A runbook explicitly identifies checks that must run elsewhere, such as VPN connectivity or public domain resolution.

7. **Prepare VM 200 as the control machine.** Connect over SSH, clone this repository, install tools, and prepare Proxmox API access.
   - [ ] [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md).
   - [ ] [Install Ansible and Terraform](runbooks/11-install-management-tools.md).
   - [ ] [Prepare Proxmox API access](runbooks/12-create-proxmox-api-token.md).
8. **Provide private VPN access.** Provision VM 250 and advertise the private subnet.
   - [ ] [Provision Tailscale access](runbooks/07-tailscale-private-access.md).
9. **Build the two Kubernetes clusters.** Prepare dev/stage VMs **201–203** and prod VMs **211–213**, then install K3s.
   - [ ] [Provision the cluster VMs](runbooks/08-provision-cluster-vms.md).
   - [ ] [Install K3s on both clusters](runbooks/09-install-k3s-clusters.md).
10. **Deploy and verify the application manifests.** Use the assigned cluster and isolated namespace for each environment; complete this step only when its deployment phase is authorized.
    - [ ] [Deploy the application manifests](runbooks/13-deploy-application-manifests.md).

11. **Install separate GitOps controllers.** After manual application acceptance, review and adopt each cluster's deployment independently.
    - [ ] [Install Argo CD and adopt the application](runbooks/14-install-argocd.md).

12. **Publish the application over HTTPS.** Configure the dedicated edge, preserve host forwarding rules, and verify all three domains and certificates.
    - [ ] [Publish application routing and TLS](runbooks/15-publish-application.md).
