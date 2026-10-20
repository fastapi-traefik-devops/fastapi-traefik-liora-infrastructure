# Prepare disaster recovery inputs

**Where:** Trusted administrator machine, before changing the replacement host. **Status:** Checklist; backup locations and restore tools have not yet been specified in this repository.

1. Record the replacement Proxmox host's **current public IPv4 address**, provider gateway, and public interface. The public IP will probably differ from the failed host. Treat it as a deployment input, not a literal embedded in scripts or runbooks.
2. Locate the existing administrator SSH private/public key pair, the verified repository revision or offline copy, Terraform state and its backups, and any cluster/application backups needed later. Preserve original copies.
3. Verify which backup and state correspond to each cluster: dev/stage (`201–203`) and prod (`211–213`). Record recovery points and the chosen state reconciliation strategy before creating VMs.
4. Confirm that the new Proxmox host is reachable through its provider console. When VM 200 is available, use the **new** public IP for the SSH client and the Proxmox API endpoint. For Terraform, supply the endpoint as a variable/environment value; do not edit scattered hardcoded example addresses as a recovery method.
5. Search the chosen repository revision and local operator configuration for the previous public IP before applying network, Terraform, DNS, or monitoring settings. Update only the components that actually use that endpoint; do not import unrelated test rules or services into the recovered design.

**Done when:** The operator has a verified recovery input list and a single recorded current public IP. No backup or Terraform state has been overwritten.
