# Current infrastructure architecture

## Host and private network

One Proxmox VE 9 host provides `vnet77` (`192.168.77.0/24`), gateway
`192.168.77.1`, and outbound NAT. Its public IPv4 address is a recovery input,
not a fixed part of the topology. Debian 13 Cloud-Init template **9013** is the
source for the managed VMs. The operator selects VM-capable disk storage on the
current host before creating the template.

| Component | VM IDs | Private address or API VIP | Provisioning |
| --- | --- | --- | --- |
| Management | 200 | `192.168.77.200` | Proxmox clone and Cloud-Init |
| Tailscale subnet router | 250 | `192.168.77.250` | Terraform VM; Ansible guest setup |
| Dev/stage K3s servers | 201–203 | `192.168.77.201–203`; VIP `192.168.77.11` | Terraform VMs; Ansible K3s |
| Prod K3s servers | 211–213 | `192.168.77.211–213`; VIP `192.168.77.12` | Terraform VMs; Ansible K3s |

## Access and cluster control

- Proxmox host nftables forwards public TCP `22200` to VM 200 port `22` for
  initial SSH access. Tailscale VM 250 advertises `192.168.77.0/24` for private
  administration after its route is approved in the tailnet.
- VM 200 holds the working checkout and runs Terraform and Ansible. Each
  Terraform module keeps its own state. Local credentials and SSH keys reside
  in ignored files under `recovery/`; that directory also contains tracked
  examples and helpers.
- Both clusters have three K3s server nodes with embedded etcd. Ansible
  installs kube-vip for each cluster's **API** VIP; remaining servers join
  through that VIP. Cluster tokens are separate and stored locally in
  `recovery/`. The playbooks do not disable K3s packaged Traefik or ServiceLB.
- The K3s VM Terraform defaults are two vCPUs and Proxmox memory ballooning
  from 2 GiB to 8 GiB. Ansible prepares the guest OS and installs the pinned
  K3s version from each inventory.
- VM 200 stores individual kubeconfigs for `dev-stage` and `prod`, then merges
  them into `~/.kube/config` with distinct contexts.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `scripts/proxmox/` | Debian template creation |
| `edge/nftables/` | Proxmox SSH DNAT examples |
| `edge/tailscale/` | Subnet router VM and Tailscale configuration |
| `infrastructure/k3s-cluster/terraform/` | Six K3s server VMs |
| `infrastructure/k3s-cluster/ansible/` | Guest preparation, two K3s clusters, kubeconfigs |
| `kubernetes/apps/liora/` | Current application manifests, environment overlays, and imported deployment history; not yet deployed on K3s |
| `recovery/` | Local recovery inputs and examples; live credentials stay out of Git |
| `runbooks/` | Operator steps for installation and recovery |

Start with the [installation](../00-Installation_from-0.md) or
[disaster recovery](../01-Disaster_recovery.md) navigator. The documented
infrastructure flow continues with the
[application deployment procedure](../runbooks/13-deploy-application-manifests.md).
The application manifests have been imported and rendered locally. No K3s
application deployment, data restoration, DNS, public routing or TLS setup has
been verified. PostgreSQL, its PVC, Adminer and prestart remain in the initial
stack; the target platform components are later work.
