# Check Proxmox VE 9

**Where:** Provider console or an administrator session on the Proxmox host.

## Confirm the host version

- [ ] Keep the provider console available. Run `pveversion` and confirm the major release is **9**.

### If the host runs Proxmox VE 8

> [!WARNING]
> Complete the [official 8-to-9 upgrade procedure](https://pve.proxmox.com/wiki/Upgrade_from_8_to_9) before continuing. Recheck `pveversion` afterward. This runbook does not replace the upgrade procedure.

## Check nftables

- [ ] Run `nft --version`.

### If nftables is not installed

> [!NOTE]
> - [ ] On Proxmox 9, run `apt update && apt install nftables`, then repeat `nft --version`.

## Project NAT scope

- [ ] Use nftables for this project's custom DNAT. Keep Proxmox packages and the host's existing firewall ruleset intact. Apply the [project examples](../edge/nftables/README.md) through the [VM 200 SSH runbook](05-configure-vm200-ssh-dnat.md).

**Done when:** Proxmox reports version 9 and `nft --version` succeeds.
