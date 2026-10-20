# Prepare disaster recovery inputs

**Where:** Trusted administrator machine, before changing the replacement host.

1. Record the replacement Proxmox host's **current public IPv4 address**, provider gateway, and public interface. Use the replacement IP as a deployment input, not a literal embedded in scripts or runbooks.
2. Locate the existing administrator SSH private/public key pair, the repository revision or offline copy, Terraform state and its backups, and the cluster/application backups. For an etcd snapshot restore, keep the original K3s server token for each cluster with its snapshot. Preserve original copies.
3. Verify which backup and state correspond to each cluster: dev/stage (`201–203`) and prod (`211–213`). Record recovery points and the chosen state reconciliation strategy before creating VMs.
4. Confirm that the new Proxmox host is reachable through its provider console. Use the **new** public IP for SSH access from your PC/laptop. On VM 200, keep the Proxmox API endpoint at `https://192.168.77.1:8006/` in `recovery/.env`.
5. Search the chosen repository revision and local operator configuration for the previous public IP before applying network, Terraform, DNS, or monitoring settings. Update only the components that actually use that endpoint; do not import unrelated test rules or services into the recovered design.

**Done when:** The operator has a verified recovery input list and a single recorded current public IP. No backup or Terraform state has been overwritten.
