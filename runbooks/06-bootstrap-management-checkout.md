# Bootstrap the repository checkout on VM 200

**Where:** Trusted administrator PC/laptop, then VM 200.

1. On the trusted client, set `PROXMOX_PUBLIC_IP` to the **current** Proxmox public IPv4 address: `read -r -p 'Current Proxmox public IPv4: ' PROXMOX_PUBLIC_IP`. During disaster recovery, obtain the replacement IP from the provider. Keep it as a runtime input rather than embedding it in scripts.
2. Connect through the VM 200 DNAT path: `ssh -i recovery/LIORA-id_ed25519 -p 22200 root-admin@"$PROXMOX_PUBLIC_IP"`. Verify that the remote host is VM 200.
3. On VM 200, install `git` if needed, then clone the repository: `git clone https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure.git`. Inspect `git remote -v` and `git rev-parse HEAD` after cloning. Work from the intended reviewed revision; during recovery, match it to the verified backups and Terraform state. Then [install Ansible and Terraform](11-install-management-tools.md) on VM 200.
4. Restore the local credential bundle into this checkout's Git-ignored `recovery/` directory on VM 200: `.env`, `LIORA-id_ed25519`, and `LIORA-id_ed25519.pub`. Keep the private key and `.env` at mode `0600`; the public key may be `0644`. If any credential was restored from an example, use `bash recovery/check_credentials.sh --tailscale` to check it before [phase 8](07-tailscale-private-access.md). Do not put a private key in any VM template or guest VM.
5. From VM 200, use the Proxmox private API endpoint `https://192.168.77.1:8006/` after confirming reachability. [Create and verify the Proxmox API token](12-create-proxmox-api-token.md) if `recovery/.env` does not already contain a valid one. Keep the ignored `recovery/` credentials, Terraform state, and recovery archives in restricted local paths. Compare Terraform plans with actual Proxmox inventory before applying; VM 200 is created directly on Proxmox and is not declared in the Terraform modules.

**Done when:** VM 200 has the verified checkout, current public IP, protected SSH identity, and a reachable private Proxmox API.
