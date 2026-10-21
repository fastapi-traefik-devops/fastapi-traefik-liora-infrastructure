# Bootstrap the repository checkout on VM 200

**Where:** Trusted administrator PC/laptop, then VM 200.

## Connect from your PC/laptop

- [ ] Set `PROXMOX_PUBLIC_IP` to the **current** Proxmox public IPv4 address: `read -r -p 'Current Proxmox public IPv4: ' PROXMOX_PUBLIC_IP`. During recovery, use the provider's replacement IP rather than editing scripts.
- [ ] Connect through VM 200's DNAT path: `ssh -i recovery/LIORA-id_ed25519 -p 22200 root-admin@"$PROXMOX_PUBLIC_IP"`. Confirm the remote host is VM 200.

## Prepare the checkout on VM 200

### If Git is not installed

> [!NOTE]
> Install `git` on VM 200 before cloning the repository.

- [ ] Clone the repository: `git clone https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure.git`.
- [ ] Check `git remote -v` and `git rev-parse HEAD`. Use the intended reviewed revision; during recovery, match it to the backups and Terraform state.
- [ ] [Install Ansible and Terraform](11-install-management-tools.md) on VM 200.

## Restore local credentials and API access

- [ ] Restore `.env`, `LIORA-id_ed25519`, and `LIORA-id_ed25519.pub` into this checkout's Git-ignored `recovery/` directory. Set the private key and `.env` to mode `0600`; the public key may be `0644`. Keep private keys out of VM templates and guest VMs.
- [ ] From VM 200, confirm the private Proxmox API endpoint `https://192.168.77.1:8006/` is reachable.
- [ ] Keep ignored credentials, Terraform state, and recovery archives in restricted local paths. Compare Terraform plans with actual Proxmox inventory before applying; VM 200 is created directly on Proxmox and is not declared in Terraform.

### If `recovery/.env` has no valid Proxmox API token

> [!NOTE]
> - [ ] [Create and verify the Proxmox API token](12-create-proxmox-api-token.md) before Terraform provisioning.

### If credentials came from an example file

> [!NOTE]
> Install the dependencies described in the [recovery schema](../recovery/README.md),
> then run `bash recovery/check_credentials.sh --tailscale` before [the Tailscale phase](07-tailscale-private-access.md).

**Done when:** VM 200 has the verified checkout, current public IP, protected SSH identity, and a reachable private Proxmox API.
