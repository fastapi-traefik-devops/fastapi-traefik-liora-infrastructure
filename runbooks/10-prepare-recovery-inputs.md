# Prepare disaster recovery inputs

**Where:** Trusted administrator machine, before changing the replacement host.

## Record the replacement host

- [ ] Record the **current public IPv4 address**, provider gateway, and public interface. Use the replacement IP as a deployment input, not a literal embedded in scripts or runbooks.
- [ ] Confirm access through the provider console. Use the new public IP for SSH from your PC/laptop. On VM 200, keep the private Proxmox API endpoint `https://192.168.77.1:8006/` in `recovery/.env`.

## Collect and match recovery artifacts

- [ ] Locate the existing administrator SSH key pair, intended repository revision or offline copy, Terraform state and its backups, and cluster and application backups. Preserve original copies.
- [ ] Match each backup and state to dev/stage (`201–203`) or prod (`211–213`). Record recovery points and the state reconciliation strategy before creating VMs.
- [ ] Search the chosen revision and local operator configuration for the old public IP. Update only components that use it before applying network, Terraform, DNS, or monitoring settings. Do not import unrelated test rules or services.

### If restoring an etcd snapshot

> [!IMPORTANT]
> Keep each cluster's original K3s server token with its matching snapshot. A fresh token cannot decrypt that snapshot.

**Done when:** The operator has a verified recovery input list and a single recorded current public IP. No backup or Terraform state has been overwritten.
