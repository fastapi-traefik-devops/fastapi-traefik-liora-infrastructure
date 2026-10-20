# Proxmox VE 9 SSH DNAT examples

The current [installation](../../00-Installation_from-0.md) and [disaster recovery](../../01-Disaster_recovery.md) paths need one public entry point before Tailscale is available: TCP port `22200` on the Proxmox host forwards to SSH on management VM `192.168.77.200:22`. The Proxmox public IP is an input to the SSH client, not a literal in the nftables rule, so it can change during recovery.

- [custom77-nat.nft.example](custom77-nat.nft.example) contains the project-owned IPv4 DNAT table for a **new** host. Verify the public-facing interface; the current host uses `vmbr0`.
- [custom77-nat.service.example](custom77-nat.service.example) reloads that file at boot when the host has no existing loader.
- [VM 200 SSH DNAT runbook](../../runbooks/05-configure-vm200-ssh-dnat.md) gives the inspection, installation, validation, and external SSH test steps.

The private `vnet77` subnet and its outbound SNAT are configured in [Proxmox SDN](../../runbooks/01-create-private-vnet.md). These examples add no public HTTP/HTTPS forwarding and do not modify Proxmox-managed firewall tables.

On an existing host, inspect `/etc/nftables.d/custom77-nat.nft` and its loader first. The live table may contain other rules; replacing it with the minimal example would remove them. Merge only the missing VM 200 rule and reuse the existing loader. Never flush the complete nftables ruleset for this step.
