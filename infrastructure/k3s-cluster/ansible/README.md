# K3s Ansible automation

Run the tested bootstrap sequence in `site.yml` separately for each cluster.
`inventory-dev-stage.yml` targets VMs 201–203 and VIP `192.168.77.11`;
`inventory-prod.yml` targets VMs 211–213 and VIP `192.168.77.12`.
Do not pass both inventories to a single run.

At the start of each run, Ansible creates a 64-character server token in
`recovery/k3s-<cluster>.token` if it is absent. Existing files are reused, so
rerunning a playbook does not rotate the token. These files are ignored by Git.
This playbook builds fresh clusters. Restoring an etcd snapshot requires its
original server token and a separate restore procedure; a new token cannot
decrypt that snapshot.

The last play in `site.yml` writes `~/.kube/config-dev-stage` or
`~/.kube/config-prod` on VM 200. The cluster, user and context names are set
directly by Ansible. After both runs, `50_merge_kubeconfigs.yml` writes
`~/.kube/config` with both named contexts.

Follow [the K3s installation runbook](../../../runbooks/09-install-k3s-clusters.md)
for commands and verification. The play order remains: prepare nodes,
bootstrap the first server, install kube-vip, join the remaining servers
through the VIP, and fetch kubeconfig.
