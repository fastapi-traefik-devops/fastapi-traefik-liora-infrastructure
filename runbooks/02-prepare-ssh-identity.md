# Prepare the administrator SSH identity

**Where:** Trusted administrator PC/laptop.

## Obtain the key pair

### New installation

- [ ] Create one Ed25519 key pair in the local `recovery/` directory only if neither file exists:

   ```sh
   test ! -e recovery/LIORA-id_ed25519 && test ! -e recovery/LIORA-id_ed25519.pub
   ssh-keygen -t ed25519 -f recovery/LIORA-id_ed25519 -C 'LIORA infrastructure administrator'
   chmod 600 recovery/LIORA-id_ed25519
   chmod 644 recovery/LIORA-id_ed25519.pub
   ```

### Disaster recovery

- [ ] Restore the existing `recovery/LIORA-id_ed25519` and `recovery/LIORA-id_ed25519.pub` from the separate encrypted credential archive. Do not regenerate them unless key rotation is deliberate.
- [ ] Check that the key files match without exposing the private key:

   ```sh
   ssh-keygen -y -f recovery/LIORA-id_ed25519 | awk '{print $1, $2}'
   awk '{print $1, $2}' recovery/LIORA-id_ed25519.pub
   ```

## Place the keys for provisioning

- [ ] Put **only the public key** into VM Cloud-Init user accounts for VM 200, the Tailscale router, and later cluster VMs. Keep private keys out of the template and guest VMs.
- [ ] Keep the private key on the trusted client; restore it into VM 200's Git-ignored `recovery/` directory for Ansible and Proxmox access. Never copy it to the router or cluster VMs.
- [ ] Verify that both `recovery/LIORA-id_ed25519*` files are Git ignored before staging files.
- [ ] Make the public key available on the Proxmox host for the manual VM 200 Cloud-Init step. Use its actual host path in the [VM 200 runbook](04-create-management-vm-200.md).

**Done when:** The key pair matches, the private key is restricted to trusted operator hosts, and the public key is ready for Cloud-Init.
