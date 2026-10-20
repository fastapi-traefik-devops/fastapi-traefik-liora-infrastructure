# Configure persistent SSH DNAT to VM 200

**Where:** Proxmox VE 9 host. **Purpose:** Public TCP `22200` → `192.168.77.200:22`. **Status:** This exact forwarding rule is present in the supplied live `/etc/nftables.d/custom77-nat.nft`; the service that reloads that file has not yet been inspected.

1. Keep provider console access open. Confirm that VM 200 runs SSH on port 22 and that `nft --version` succeeds. Identify the actual public-facing interface; the supplied live rule uses `vmbr0`.
2. Inspect `/etc/nftables.d/custom77-nat.nft` and `nft list table ip custom77_nat`. If the rule below already exists, keep it; do not add a duplicate. **Do not replace the live file with a minimal example:** it may contain other working rules.
3. On a replacement host, create `/etc/nftables.d/custom77-nat.nft` if it does not exist. Put the rule in a project-owned IPv4 NAT table and prerouting chain. If the file already exists, add only the missing rule inside its existing chain, preserving every other entry:

   ```nft
   destroy table ip custom77_nat
   table ip custom77_nat {
       chain prerouting {
           type nat hook prerouting priority dstnat; policy accept;
           iifname "vmbr0" tcp dport 22200 dnat to 192.168.77.200:22 comment "SSH to VM 200"
       }
   }
   ```

4. Check the **complete** file with `nft -c -f /etc/nftables.d/custom77-nat.nft`. Apply it with `nft -f /etc/nftables.d/custom77-nat.nft` only after the check passes, then inspect `nft list table ip custom77_nat`. Never use `flush ruleset` here.
5. Check whether an existing systemd unit already reloads this file. Reuse that unit if present. On a new host without a loader, create `/etc/systemd/system/custom77-nat.service`:

   ```ini
   [Unit]
   Description=Load custom77 nftables DNAT rules
   After=network-online.target
   Wants=network-online.target
   Before=pve-guests.service

   [Service]
   Type=oneshot
   ExecStart=/usr/sbin/nft -f /etc/nftables.d/custom77-nat.nft
   ExecReload=/usr/sbin/nft -f /etc/nftables.d/custom77-nat.nft
   RemainAfterExit=yes

   [Install]
   WantedBy=multi-user.target
   ```

   Run `systemctl daemon-reload` and `systemctl enable --now custom77-nat.service`; verify `systemctl status custom77-nat.service`. Do not enable a second loader for the same table on an existing host.
6. On the trusted client, set `PROXMOX_PUBLIC_IP` to the host's current public IPv4 address. Test from an external connection with `ssh -p 22200 root-admin@"$PROXMOX_PUBLIC_IP"`. Confirm the host forwarding/firewall path and VM return path if it fails. Verify the rule survives a controlled reboot when a reboot is scheduled; a syntax check alone does not prove persistence.

**Recovery IP change:** This DNAT rule matches `vmbr0` and port `22200`, so it contains no old public IP. Use the replacement host's current public IP in SSH clients and any other endpoint configuration. Do not copy unrelated live rules from the supplied example into a new installation.
