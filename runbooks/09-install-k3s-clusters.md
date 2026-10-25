# Install the two K3s clusters

**Where:** Run every command on management VM 200, from the repository root.

## Cluster layout

| Cluster | VM IDs | Node IPs | API VIP | Inventory |
| --- | --- | --- | --- | --- |
| dev/stage | 201–203 | `192.168.77.201–203` | `192.168.77.11` | `inventory-dev-stage.yml` |
| prod | 211–213 | `192.168.77.211–213` | `192.168.77.12` | `inventory-prod.yml` |

## Preflight on VM 200

- [ ] Complete [VM provisioning](08-provision-cluster-vms.md). VM 200 is not a cluster node. Check SSH access with the Ansible ping commands below.
- [ ] Confirm `root-admin` exists on the clones, the recovery SSH key is authorized, and the guest NIC is `eth0`.
- [ ] Review the pinned K3s and kube-vip versions in both inventories before deploying.

This playbook builds fresh clusters. Ansible creates a different server token for each cluster on its first run and reuses the saved value later:

   ```text
   recovery/k3s-dev-stage.token
   recovery/k3s-prod.token
   ```

Preserve these ignored token files with future datastore backups.

### If restoring an etcd snapshot

- [ ] Use [the K3s etcd snapshot restore runbook](21-restore-k3s-etcd-snapshot.md)
      with the matching snapshot and original server token. Do not run the
      fresh bootstrap commands below for that cluster.

- [ ] Install the playbook dependency and inspect each target list. Use the administrator private key restored to `recovery/LIORA-id_ed25519` on VM 200.

   ```sh
   ansible-galaxy collection install -r infrastructure/k3s-cluster/ansible/requirements.yml
   ansible-inventory -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml --graph
   ansible-inventory -i infrastructure/k3s-cluster/ansible/inventory-prod.yml --graph
   ```

### If VMs were recreated at the same IPs

> [!NOTE]
> Confirm the VM-to-IP mapping in Proxmox and remove their old SSH host keys from VM 200. This command covers all six nodes; for a partial rebuild, list only affected IPs.

- [ ] Remove the affected old entries:

   ```sh
   for ip in 192.168.77.{201..203} 192.168.77.{211..213}; do
     ssh-keygen -R "$ip"
   done
   ```

- [ ] Check access to both inventories with the restored private key:

   ```sh
   ansible k3s_servers -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml -m ping --private-key recovery/LIORA-id_ed25519
   ansible k3s_servers -i infrastructure/k3s-cluster/ansible/inventory-prod.yml -m ping --private-key recovery/LIORA-id_ed25519
   ```

### If Ansible reports `Permission denied (publickey)`

> [!WARNING]
> Check that the matching public key is authorized for `root-admin` on the VM. This is an authentication failure, not a `known_hosts` failure.

## Install dev/stage and prod

Run each cluster with its own inventory, VIP, and token. Do not combine the inventories in one run.

- [ ] Install dev/stage, then prod:

   ```sh
   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/site.yml

   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-prod.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/site.yml
   ```

The playbook installs K3s without starting it, then starts the service and checks each node's local API readiness up to 60 times, 10 seconds apart. Each API request has a 10-second timeout. A failed first systemd start can recover through systemd's automatic restart without failing the Ansible run.

### If K3s does not become ready after the retries

> [!WARNING]
> Inspect the affected node's K3s journal before rerunning the playbook. Do not recreate the VM or rotate the cluster token solely because startup timed out.

- [ ] From VM 200, replace `<node-ip>` with the affected node's address and inspect its service status and recent logs:

   ```sh
   ssh -i recovery/LIORA-id_ed25519 root-admin@<node-ip> \
     'sudo systemctl status k3s --no-pager -l; sudo journalctl -u k3s -b -n 100 --no-pager'
   ```

### If only kubeconfig retrieval fails

> [!NOTE]
> After node tasks complete, rerun only the kubeconfig play. It uses `slurp` and a delegated `copy` task; no cluster reinstall is needed.

- [ ] Rerun the kubeconfig play:

   ```sh
   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-prod.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/40_fetch_kubeconfig.yml
   ```

### If a kubeconfig is owned by root

> [!WARNING]
> Repair only the affected directory and file on VM 200, then rerun the kubeconfig play. The current inventories leave privilege escalation to remote plays; local kubeconfig tasks run without it.

- [ ] Repair the affected file:

   ```sh
   sudo chown "$(id -u):$(id -g)" "$HOME/.kube" "$HOME/.kube/config-prod"
   chmod 700 "$HOME/.kube"
   chmod 600 "$HOME/.kube/config-prod"
   ```

Apply the same ownership repair to `config-dev-stage` only if that file is root-owned.

## Merge kubeconfigs and verify clusters

The merge playbook checks both identities and API VIPs before writing `~/.kube/config`. Individual `config-dev-stage` and `config-prod` files remain available.

- [ ] Merge and verify from VM 200:

   ```sh
   ansible-playbook -i localhost, -c local \
     infrastructure/k3s-cluster/ansible/50_merge_kubeconfigs.yml
   kubectl config get-contexts
   kubectl --context dev-stage get nodes -o wide
   kubectl --context prod get nodes -o wide
   ```

Expect contexts `dev-stage` and `prod`, users `admin-dev-stage` and `admin-prod`, and default context `dev-stage`. Specify `--context` for commands targeting a particular cluster.

**Done when:** Both inventories complete, all six nodes are Ready in their
respective clusters, the two API VIPs answer independently, and VM 200 has
readable `config-dev-stage`, `config-prod`, and merged named contexts.
