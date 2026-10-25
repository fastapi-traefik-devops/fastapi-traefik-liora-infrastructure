# Prepare the administrator SSH identity

**Where:** Trusted administrator laptop, in the infrastructure repository root.

## Check the archived key pair

- [ ] Unpack `recovery/LIORA-id_ed25519` and
      `recovery/LIORA-id_ed25519.pub` from the encrypted credentials archive
      into this checkout. Use the same pair for installation and recovery.
- [ ] Set the private key mode: `chmod 600 recovery/LIORA-id_ed25519`.
- [ ] Check that the key files match without exposing the private key:

   ```bash
   test -s recovery/LIORA-id_ed25519
   test -s recovery/LIORA-id_ed25519.pub
   diff -u \
     <(ssh-keygen -y -f recovery/LIORA-id_ed25519 | awk '{print $1, $2}') \
     <(awk '{print $1, $2}' recovery/LIORA-id_ed25519.pub)
   ```

   Continue only if `diff` prints no differences and exits with status 0.

## Place the keys for provisioning

- [ ] Use **only the public key** for VM Cloud-Init accounts. Keep the private
      key on the laptop and, after VM 200 exists, in its Git-ignored
      `recovery/` directory. Do not copy the private key to Proxmox, the
      router, the template, or cluster VMs.
- [ ] Verify that both key files are Git ignored before staging files:

   ```sh
   git check-ignore recovery/LIORA-id_ed25519 recovery/LIORA-id_ed25519.pub
   ```
- [ ] Copy **only the public key** to the Proxmox host with the provider's
      root SSH access. On a new host, the LIORA key may not yet be
      authorized for root. `/root` below is the Proxmox root home, not
      VM 200's home:

   ```sh
   read -r -p 'Current Proxmox public IPv4: ' PROXMOX_PUBLIC_IP
   scp recovery/LIORA-id_ed25519.pub \
     root@"$PROXMOX_PUBLIC_IP":/root/LIORA-id_ed25519.pub
   ```

   Confirm the destination with
   `ssh root@"$PROXMOX_PUBLIC_IP" 'ls -l /root/LIORA-id_ed25519.pub'`.
   If the provider supplied a separate SSH key, add
   `-i /path/to/provider-key` to both commands.
   The [VM 200 runbook](04-create-management-vm-200.md) uses that exact path.

**Done when:** The key pair matches, the private key is restricted to trusted operator hosts, and the public key is ready for Cloud-Init.
