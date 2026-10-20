# Install the two K3s clusters

**Where:** Run every command on management VM 200, from the repository root.

| Cluster | VM IDs | Node IPs | API VIP | Inventory |
| --- | --- | --- | --- | --- |
| dev/stage | 201–203 | `192.168.77.201–203` | `192.168.77.11` | `inventory-dev-stage.yml` |
| prod | 211–213 | `192.168.77.211–213` | `192.168.77.12` | `inventory-prod.yml` |

1. Complete [VM provisioning](08-provision-cluster-vms.md) and verify SSH
   access from VM 200 to all six nodes. VM 200 is not a cluster node. Check
   that `root-admin` exists on the clones, the recovery SSH key is authorized,
   and the guest NIC is `eth0`. Review the pinned K3s and kube-vip versions
   in both inventories before deploying.

2. This playbook builds fresh clusters. Ansible generates a different server
   token for each cluster on its first run and saves it under `recovery/`.
   Subsequent runs reuse the saved value:

   ```text
   recovery/k3s-dev-stage.token
   recovery/k3s-prod.token
   ```

   Preserve these ignored token files with future datastore backups.

3. Install the playbook dependency and inspect each target list. Use the
   administrator private key restored to `recovery/LIORA-id_ed25519` on VM 200.

   ```sh
   ansible-galaxy collection install -r infrastructure/k3s-cluster/ansible/requirements.yml
   ansible-inventory -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml --graph
   ansible-inventory -i infrastructure/k3s-cluster/ansible/inventory-prod.yml --graph
   ```

   If these VMs replace earlier machines at the same IPs, confirm the VM-to-IP
   mapping in Proxmox and remove their old SSH host keys from VM 200. This
   command covers a rebuild of all six nodes; for a partial rebuild, list only
   the affected IPs:

   ```sh
   for ip in 192.168.77.{201..203} 192.168.77.{211..213}; do
     ssh-keygen -R "$ip"
   done
   ```

   Check access to both inventories with the restored private key:

   ```sh
   ansible k3s_servers -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml -m ping --private-key recovery/LIORA-id_ed25519
   ansible k3s_servers -i infrastructure/k3s-cluster/ansible/inventory-prod.yml -m ping --private-key recovery/LIORA-id_ed25519
   ```

   If SSH still reports `Permission denied (publickey)`, check that the
   matching public key is authorized for `root-admin` on the VM. This is an
   authentication failure, not a `known_hosts` failure.

4. Install dev/stage, then prod. Each invocation uses only its own inventory,
   VIP and saved token. Do not combine the two inventories in one run.

   ```sh
   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-dev-stage.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/site.yml

   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-prod.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/site.yml
   ```

   If the node tasks have completed and only the kubeconfig fetch failed,
   rerun that play alone. It reads the remote kubeconfig with `slurp` and
   writes the named file on VM 200 with a delegated `copy` task. No temporary
   kubeconfig file or cluster reinstall is needed.

   ```sh
   ansible-playbook -i infrastructure/k3s-cluster/ansible/inventory-prod.yml \
     --private-key recovery/LIORA-id_ed25519 \
     infrastructure/k3s-cluster/ansible/40_fetch_kubeconfig.yml
   ```

   If a prior run created a root-owned kubeconfig, repair only the affected
   directory and file on VM 200, then rerun the kubeconfig play:

   ```sh
   sudo chown "$(id -u):$(id -g)" "$HOME/.kube" "$HOME/.kube/config-prod"
   chmod 700 "$HOME/.kube"
   chmod 600 "$HOME/.kube/config-prod"
   ```

   The current inventories leave privilege escalation to the remote plays;
   local kubeconfig tasks explicitly run without escalation. Apply the same
   ownership repair to `config-dev-stage` if that file was created as root.

5. Merge the named kubeconfigs into the default `~/.kube/config` on VM 200.
   The merge playbook checks both identities and API VIPs before writing.
   The individual `config-dev-stage` and `config-prod` files remain available.
   Use `kubectl` on VM 200 for the verification commands below.

   ```sh
   ansible-playbook -i localhost, -c local \
     infrastructure/k3s-cluster/ansible/50_merge_kubeconfigs.yml
   kubectl config get-contexts
   kubectl --context dev-stage get nodes -o wide
   kubectl --context prod get nodes -o wide
   ```

   Expect contexts `dev-stage` and `prod`, users `admin-dev-stage` and
   `admin-prod`, and default context `dev-stage`. Specify `--context` for
   commands that target a particular cluster.

**Disaster recovery:** A fresh cluster build generates or reuses the local
tokens and does not restore application data. To restore an etcd snapshot,
use its original server token and the K3s restore procedure. See
the [K3s backup and restore requirements](https://docs.k3s.io/datastore/backup-restore).
