# Proxmox and K3s infrastructure

This repository documents the Proxmox VE 9 host and management VM setup, then
provisions a Tailscale subnet router and two three-node K3s clusters.

## Infrastructure at a glance

| Component | VM IDs | Addresses |
| --- | --- | --- |
| Proxmox gateway | — | `192.168.77.1` |
| Management | 200 | `192.168.77.200` |
| Application edge | 240 | `192.168.77.240` |
| Tailscale router | 250 | `192.168.77.250` |
| Dev/stage K3s | 201–203 | `192.168.77.201–203`; API VIP `192.168.77.11` |
| Prod K3s | 211–213 | `192.168.77.211–213`; API VIP `192.168.77.12` |

Each K3s cluster has three server nodes with embedded etcd. The Debian 13
Cloud-Init template is VM `9013`.

## Start here

- [New installation](00-Installation_from-0.md)
- [Infrastructure disaster recovery](01-Disaster_recovery.md)

Both navigators link to the step-specific instructions in `runbooks/`.
The [application deployment runbook](runbooks/13-deploy-application-manifests.md)
describes the manual deployment gates. [DEV](docs/testreports/PHASE3_REPORT.md),
[STAGE](docs/testreports/PHASE4_REPORT.md), and [PROD](docs/testreports/PHASE5_REPORT.md)
are deployed and privately verified, including mutual database and token
isolation. PROD runs two backend and two frontend replicas with the approved
STAGE image digests. [Separate Argo CD instances](docs/testreports/PHASE6_REPORT.md)
now reconcile each cluster, with verified self-healing and PROD pruning disabled.
[Public HTTPS routing](docs/testreports/PHASE7_REPORT.md) now serves
[PROD](https://liora.aprt.info), [DEV](https://dev.liora.aprt.info), and
[STAGE](https://stage.liora.aprt.info) through the dedicated HAProxy edge, with
trusted certificates and DNS-only records. Cloudflare proxy mode remains unverified.

For the implemented topology and component boundaries, see
[Current architecture](docs/ARCHITECTURE.md).

## Repository layout

```text
edge/tailscale/                 Tailscale VM and router configuration
edge/haproxy/                   Application edge VM, routing and TLS distribution
edge/nftables/                 Proxmox host DNAT examples
infrastructure/k3s-cluster/    Terraform VMs and Ansible K3s installation
kubernetes/apps/liora/         Application base, overlays, and source history
kubernetes/gitops/argocd/      Independent nonprod/PROD GitOps bootstrap
docs/testreports/              Implementation plans and phase reports
runbooks/                      Operator instructions
recovery/                      Credential examples and local, ignored secrets
scripts/proxmox/               Proxmox host scripts
```

## Keep credentials and state outside Git

Real credentials, SSH private keys, Terraform state, and recovery archives must
remain outside Git. The local `recovery/` directory holds ignored copies needed
by the operator; review `git status` before every commit.

The [recovery schema and validator](recovery/README.md) describe every supported
input, dependency setup, warning policy and exit code. Run the complete offline
check before deployment and review unknown-field warnings without deleting data.
