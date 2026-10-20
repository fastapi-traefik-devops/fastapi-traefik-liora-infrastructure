# Prepare the administrator SSH identity

**Where:** Trusted administrator PC/laptop. **Status:** Recovery key pair checked locally; new-install generation has not been replayed.

1. For a new installation, create one Ed25519 key pair in the local `recovery/` directory, only if neither file exists:

   ```sh
   test ! -e recovery/LIORA-id_ed25519 && test ! -e recovery/LIORA-id_ed25519.pub
   ssh-keygen -t ed25519 -f recovery/LIORA-id_ed25519 -C 'LIORA infrastructure administrator'
   chmod 600 recovery/LIORA-id_ed25519
   chmod 644 recovery/LIORA-id_ed25519.pub
   ```

2. For disaster recovery, restore the existing `recovery/LIORA-id_ed25519` and `recovery/LIORA-id_ed25519.pub` from the separate encrypted credential archive. Do not regenerate them unless key rotation is deliberate. Check that they match without exposing the private key:

   ```sh
   ssh-keygen -y -f recovery/LIORA-id_ed25519 | awk '{print $1, $2}'
   awk '{print $1, $2}' recovery/LIORA-id_ed25519.pub
   ```

3. Put **only the public key** into VM Cloud-Init user accounts. Use it for VM 200, the Tailscale router, and later cluster VMs. The template should not contain an administrator private key. Keep the private key on the trusted client; restore it into VM 200's Git-ignored `recovery/` directory for the Ansible and Proxmox access steps that run there. Never copy it to the router or cluster VMs. Both `recovery/LIORA-id_ed25519*` files are Git ignored; verify that before staging files.
4. Make the public key available on the Proxmox host for the manual VM 200 Cloud-Init step. Use its actual host path in the [VM 200 runbook](04-create-management-vm-200.md).

**Done when:** The key pair matches, the private key is restricted to trusted operator hosts, and the public key is ready for Cloud-Init.
