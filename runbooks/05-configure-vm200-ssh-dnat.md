# Configure persistent SSH DNAT to VM 200

**Where:** Proxmox VE 9 host. **Purpose:** Public TCP `22200` → `192.168.77.200:22`.

## Inspect the host

- [ ] Keep provider console access open. Confirm VM 200 runs SSH on port 22 and `nft --version` succeeds.
- [ ] Identify the public-facing interface; the current live rule uses `vmbr0`.
- [ ] Inspect `/etc/nftables.d/custom77-nat.nft` and `nft list table ip custom77_nat` before editing.

### If the DNAT table already exists

> [!IMPORTANT]
> Keep any working VM 200 rule. Do not add a duplicate or replace the live file with the minimal [example](../edge/nftables/custom77-nat.nft.example); it may contain other rules. Add only a missing rule inside the existing prerouting chain.

## Configure the VM 200 rule

### If the DNAT table is absent

> [!NOTE]
> Use the [new-host example](../edge/nftables/custom77-nat.nft.example). It forwards TCP `22200` to `192.168.77.200:22` without embedding the public IP.

- [ ] On a new host without the table, adapt the public interface and install the example as `/etc/nftables.d/custom77-nat.nft`. On an existing host, add only the missing rule to that file:

   ```nft
   # Proxmox VE 9 example for a new host. Adapt the public-facing interface.
   # This reloads only custom77_nat. Preserve any other rules already in that table
   # before using this file on an existing host.
   destroy table ip custom77_nat

   table ip custom77_nat {
       chain prerouting {
           type nat hook prerouting priority dstnat; policy accept;

           # Public TCP 22200 reaches SSH on management VM 200.
           iifname "vmbr0" tcp dport 22200 dnat to 192.168.77.200:22 comment "SSH to VM 200"
       }
   }
   ```

### Validate the active rule

- [ ] Check the **complete** file with `nft -c -f /etc/nftables.d/custom77-nat.nft`. Apply it with `nft -f /etc/nftables.d/custom77-nat.nft` only after the check passes. Inspect `nft list table ip custom77_nat`. Never use `flush ruleset` here.

## Persist the rule across reboot

- [ ] Check whether a systemd unit already reloads this file.

### If the host has no loader

> [!NOTE]
> Install [custom77-nat.service.example](../edge/nftables/custom77-nat.service.example) as `/etc/systemd/system/custom77-nat.service`.

- [ ] Only on a host without a loader, install and enable the service:

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

- [ ] If you installed the service, run `systemctl daemon-reload` and `systemctl enable --now custom77-nat.service`; verify `systemctl status custom77-nat.service`.

### If a loader already exists

> [!WARNING]
> Reuse the existing loader. Do not enable a second loader for the same table.

## Verify external access

- [ ] On the trusted client, set `PROXMOX_PUBLIC_IP` to the host's current public IPv4 address. Test from an external connection with `ssh -p 22200 root-admin@"$PROXMOX_PUBLIC_IP"`.
- [ ] Verify the rule survives a controlled reboot when one is scheduled; a syntax check alone does not prove persistence.

### If the external SSH test fails

> [!WARNING]
> Check the host forwarding and firewall path, then VM 200's return path.

### If the public IP changed during recovery

> [!NOTE]
> The DNAT rule matches the interface and port, so it contains no old public IP. Use the replacement IP in SSH clients and other endpoint settings. The [nftables examples](../edge/nftables/README.md) cover only this bootstrap SSH path; do not copy unrelated live rules.
