# Prepare disaster recovery inputs

**Where:** Trusted administrator laptop, before changing the replacement host.

## Record the replacement host

- [ ] Record the current public IPv4 address, provider gateway, and public
      interface. Use the address as an input; do not edit it into scripts.
- [ ] Check provider console and root SSH access. After VM 200 exists,
      keep its private Proxmox API endpoint
      `https://192.168.77.1:8006/` in `recovery/.env`.

## Collect and match recovery artifacts

- [ ] Obtain the encrypted recovery bundle and its separately stored password.
      [Unpack it on the laptop](25-unpack-credentials-zip.md). Keep the source
      archive intact and exclude the working copy from Git.
- [ ] Record the archive checksum. Compare it with the checksum in the
      off-host backup inventory, if one is available:

```sh
read -r -p 'Encrypted archive path: ' archive_path
test -f "$archive_path" && sha256sum -- "$archive_path"
```
- [ ] Locate the administrator SSH key pair, selected repository revision,
      Terraform state, and cluster/application backups. Preserve the originals.
- [ ] Match each backup and state file to NONPROD (`201–203`) or PROD
      (`211–213`). Record the selected recovery point before creating VMs.
- [ ] Search the selected checkout and private environment file for the old
      public IP. The command lists file names only; inspect each match before
      changing it. Update the current IP in deployment inputs and the three
      application DNS records, preserving unrelated forwarding rules:

```sh
read -r -p 'Previous Proxmox public IPv4: ' OLD_PROXMOX_PUBLIC_IP
search_paths=(README.md 00-Installation_from-0.md 01-Disaster_recovery.md runbooks edge infrastructure kubernetes)
if [[ -f recovery/.env ]]; then search_paths+=(recovery/.env); fi
rg -l -F -- "$OLD_PROXMOX_PUBLIC_IP" "${search_paths[@]}"
```

### If restoring an etcd snapshot

> [!IMPORTANT]
> Keep each cluster's original K3s server token with its matching snapshot. A fresh token cannot decrypt that snapshot.

## Select the recovery route

- [ ] Match application database backups to their R2 prefix, archive identity, physical backup and WAL target. Do not run fresh initialization before recovery.
- [ ] Match Jenkins home archives to controller/plugin versions and mounted private configuration. Database backups do not contain Jenkins state.
- [ ] Record which components will be restored and which will be recreated from Git using the [recovery inventory](../01-Disaster_recovery.md#2-select-recovery-artifacts).
- [ ] Keep archived keys and old state immutable while creating working recovery copies.

**Done when:** The operator has a matched recovery input list and a single recorded current public IP. No backup or Terraform state has been overwritten.
