# Check Proxmox VE 9

**Where:** Provider console or an existing administrator session on the Proxmox host. **Status:** Documentation draft; no host changes performed by this repository.

1. Keep the provider console available while checking the host. Run `pveversion` and confirm the major release is **9**.
2. If the host is on Proxmox VE **8**, complete the [official 8-to-9 upgrade procedure](https://pve.proxmox.com/wiki/Upgrade_from_8_to_9) before using the following runbooks. Recheck `pveversion` after the upgrade. This runbook does not replace the upgrade procedure.
3. Check that the nftables CLI is available with `nft --version`. If missing, install it on Proxmox 9 with `apt update && apt install nftables`.
4. Use nftables for this project's custom DNAT. Do not remove Proxmox packages or flush the host's complete firewall ruleset as part of this change. The [project nftables examples](../edge/nftables/README.md) are applied through [the VM 200 SSH runbook](05-configure-vm200-ssh-dnat.md).

**Done when:** Proxmox reports version 9 and `nft --version` succeeds.
