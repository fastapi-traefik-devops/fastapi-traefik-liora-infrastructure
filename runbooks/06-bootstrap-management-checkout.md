# Bootstrap the repository checkout on VM 200

**Where:** Trusted administrator PC/laptop, then VM 200.

## Connect from your PC/laptop

- [ ] From the infrastructure checkout on the laptop, set the **current**
      Proxmox public IPv4 address and connect as `root-admin`:

   ```sh
   read -r -p 'Current Proxmox public IPv4: ' PROXMOX_PUBLIC_IP
   ssh -i recovery/LIORA-id_ed25519 -p 22200 root-admin@"$PROXMOX_PUBLIC_IP"
   ```

- [ ] Confirm `whoami` prints `root-admin` and `pwd` is under
      `/home/root-admin`. Do not run repository commands as root.

## Prepare the checkout on VM 200

- [ ] On VM 200, install Git if needed: `sudo apt-get update && sudo apt-get install -y git`.
- [ ] Check `$HOME/fastapi-traefik-liora-infrastructure`. If it already
      exists, inspect `git remote -v` and `git rev-parse HEAD` there.
      Do not clone over it.
- [ ] If the directory is absent, clone infrastructure into it:

   ```sh
   cd "$HOME"
   git clone https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure.git fastapi-traefik-liora-infrastructure
   cd "$HOME/fastapi-traefik-liora-infrastructure"
   git remote -v
   git rev-parse HEAD
   ```

- [ ] For disaster recovery, select the recorded infrastructure revision
      that matches the saved state and backups.
- [ ] If the next procedure needs application source, check
      `$HOME/fastapi-traefik-liora-application`. Clone only if absent:

   ```sh
   cd "$HOME"
   git clone https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application.git fastapi-traefik-liora-application
   ```

Install Ansible and Terraform after this checkout is ready, as the next
step in the installation or recovery navigator.

## Transfer the protected inputs

- [ ] Exit the VM 200 SSH session. From the laptop's infrastructure checkout,
      transfer the **Git-ignored files** in `recovery/`. This includes
      `.env`, `recovery.yaml`, the SSH pair, and any ignored credentials
      present in the archive. It does not replace tracked runbook or script files:

   ```sh
   git ls-files --others --ignored --exclude-standard -z recovery/ |
     tar --null -T - -cf - |
     ssh -i recovery/LIORA-id_ed25519 -p 22200 root-admin@"$PROXMOX_PUBLIC_IP" \
       'tar -C "$HOME/fastapi-traefik-liora-infrastructure" -xf -'
   ```

- [ ] Reconnect as `root-admin`. Enter
      `$HOME/fastapi-traefik-liora-infrastructure`; set private file modes
      and verify the required files exist:

   ```sh
   cd "$HOME/fastapi-traefik-liora-infrastructure"
   chmod 700 recovery
   chmod 600 recovery/.env recovery/recovery.yaml recovery/LIORA-id_ed25519
   test -s recovery/LIORA-id_ed25519.pub
   git check-ignore recovery/.env recovery/recovery.yaml recovery/LIORA-id_ed25519
   ```

- [ ] Check that the private Proxmox API endpoint
      `https://192.168.77.1:8006/` is reachable from VM 200.
- [ ] Keep Terraform state and recovery archives in restricted local paths.
      Compare Terraform plans with actual Proxmox inventory before applying;
      VM 200 is created directly on Proxmox.

### If `recovery/.env` has no valid Proxmox API token

> [!NOTE]
> - [ ] [Create and verify the Proxmox API token](12-create-proxmox-api-token.md) before Terraform provisioning.

**Done when:** VM 200 has the selected infrastructure checkout, the required
ignored recovery files, and access to the private Proxmox API.
