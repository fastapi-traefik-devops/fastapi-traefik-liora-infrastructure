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
| Application edge | 240 | `192.168.77.240` | Terraform VM; Ansible HAProxy |
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
| `kubernetes/apps/liora/` | Current application manifests, environment overlays, and imported deployment history; DEV/STAGE/PROD deployed and privately verified |
| `recovery/` | Local recovery inputs and examples; live credentials stay out of Git |
| `runbooks/` | Operator steps for installation and recovery |

Start with the [installation](../00-Installation_from-0.md) or
[disaster recovery](../01-Disaster_recovery.md) navigator. The documented
infrastructure flow continues with the
[application deployment procedure](../runbooks/13-deploy-application-manifests.md).
DEV and STAGE run in `app-dev` and `app-stage` on the dev/stage cluster. PROD
runs in `app-prod` on its separate cluster, with two backend and two frontend
replicas. Each environment retains PostgreSQL, its separate 1Gi local-path PVC,
Adminer, prestart, backend and frontend from the imported stack. All backend
Pods use one worker; PROD required the same explicit command as DEV/STAGE.

Database readiness, migrations, private UI login and item persistence are
verified in the [Phase 3](testreports/PHASE3_REPORT.md),
[Phase 4](testreports/PHASE4_REPORT.md), and [Phase 5](testreports/PHASE5_REPORT.md)
reports. All three environments passed mutual database-marker and token
isolation checks; synthetic acceptance items were removed afterward. Data
restoration and target platform replacements remain later work. Public HTTPS
routing is now verified in Phase 7 below.

## GitOps ownership

Independent Argo CD v3.5.6 installations in each cluster's `argocd` namespace
source this infrastructure repository. Nonprod manages app-dev/app-stage; PROD
manages app-prod. Each destination is the local Kubernetes API. Separate roots
manage the cluster-specific Application and AppProject definitions; no external
cluster credentials or shared ApplicationSet are configured.

Both roots and all children have automated reconciliation and self-healing.
Nonprod child pruning is enabled after inventory review; PROD and both roots
keep pruning off. Database PVC retention annotations remain. Registry and
application Secrets stay external prerequisites. The controllers have the
upstream cluster RBAC; AppProject restrictions scope applications rather than
providing a controller service-account boundary against cluster administrators.

Private Argo CD UI access, root/child reconciliation, hook migrations and
ConfigMap drift correction passed in the [Phase 6 report](testreports/PHASE6_REPORT.md).
Use [runbook 14](../runbooks/14-install-argocd.md) for bootstrap and adoption,
including the manual-policy render required before enabling a fresh deployment.

## Public application ingress and certificates

All three application hostnames resolve directly to the current Proxmox public
origin (`151.115.96.5` at acceptance), using Cloudflare DNS-only records. Proxmox
forwards public TCP 80/443 to dedicated HAProxy VM 240. Existing SSH and unrelated
forwarding rules remain intact. HAProxy allows the three application Host/SNI
names and rejects unknown/admin names; Argo CD and Adminer gain no public route.

TLS passes through to Traefik over disjoint ServiceLB node endpoint pools:
nonprod `.201`–`.203`, PROD `.211`–`.213`. API VIPs `.11`/`.12` are not ingress
addresses. Dedicated floating ingress VIPs and a second edge are not installed.
This is a single-edge deployment without a tested failover/reboot guarantee.

Certbot HTTP-01 on the edge issues separate trusted certificates for DEV, STAGE
and PROD. The management VM's daily certificate-sync service privately fetches
and validates each pair and updates only that environment's `app-tls` Secret.
Certbot renewal simulations and a service execution passed; a later scheduled
renewal/distribution cycle has not yet occurred. Certificate state and Terraform
state remain external operator data. DEV's HTTPS origin/CORS is active in its
restarted backend; STAGE/PROD retain their existing HTTPS settings.

The operator confirmed external warning-free loads of all three URLs. Canonical
HTTPS UI persistence, health, redirects and mutual database/token isolation
passed. See [Phase 7](testreports/PHASE7_REPORT.md) and
[runbook 15](../runbooks/15-publish-application.md). Cloudflare's proxy/Full (strict)
path remains optional follow-up and was not part of this DNS-only acceptance.
