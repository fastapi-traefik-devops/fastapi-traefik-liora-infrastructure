# Proxmox and K3s infrastructure

This repository contains the infrastructure and operator procedures for a
Proxmox VE 9 host, a management VM, a Tailscale subnet router, and two
three-node K3s clusters. It also contains the Kubernetes platform, application
deployment configuration, GitOps, CI infrastructure, and backup procedures.
The infrastructure is reusable, but its configuration is optimized for and
tested with the separate [Liora application repository](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application).

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

- [Documentation index](docs/README.md)
- [Documentation structure and maintenance](docs/docs-structure.md)

- [New installation](00-Installation_from-0.md)
- [Infrastructure disaster recovery](01-Disaster_recovery.md)

Use the [operator procedure index](runbooks/README.md) to select fresh deployment,
disaster recovery or routine backup/recovery operations. The manuals separate
empty database initialization from data restoration and isolated PITR exercises.

- [Infrastructure cost estimate](INFRASTRUCTURE_COST_ESTIMATE.md): European hosting comparison, paid services and three operating budgets.
- [Architecture](docs/ARCHITECTURE.md): desired topology, ownership and delivery policy.
- [Infrastructure diagrams](docs/project-schemes.drawio): editable topology, cluster, traffic, CI/CD, backup, monitoring and recovery views.
- [PostgreSQL backup operations](runbooks/19-cnpg-r2-backup-pitr.md): scheduled/manual cycles and failure recovery.
- [Etcd snapshot operations](docs/operations/ETCD_BACKUPS.md): native K3s snapshots, R2 retention and optional datastore recovery.
- [Backup verification](docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md): monthly isolated PITR and WAL-delivery measurements.
- [Monitoring operations](docs/operations/SLACK_ALERTING.md): alert response and notification delivery.
- [Recovery input schema](recovery/README.md): credentials, keys and generated access profiles.
- [Implementation reports](docs/testreports/README.md): phase status, migration history, evidence and remaining capabilities.
- [CI/CD](docs/CI_CD.md): Jenkins → GHCR → GitOps pipeline, setup from zero, daily use and troubleshooting.

## Repository layout

```text
edge/tailscale/                 Tailscale VM and router configuration
edge/haproxy/                   Application edge VM and TLS passthrough routing
edge/nftables/                 Proxmox host DNAT examples
infrastructure/k3s-cluster/    Terraform VMs and Ansible K3s installation
kubernetes/apps/liora/         Application base, overlays, and source history
kubernetes/gitops/argocd/      Independent nonprod/PROD GitOps bootstrap
kubernetes/platform/          Cluster platform configuration and source history
docs/testreports/              Implementation plans, phase reports, and evidence
runbooks/                      Operator instructions
recovery/                      Credential examples and local, ignored secrets
scripts/proxmox/               Proxmox host scripts
.local-work/                   Ignored tools/cache and protected private operator data
```

Prepare management and operator tools using [runbook 11](runbooks/11-install-management-tools.md).
`.local-work/` contains disposable tools/cache **and private recovery inputs**;
classify and preserve private data using [the recovery checklist](recovery/README.md#private-operator-data) before cleanup.

## Keep credentials and state outside Git

Real credentials, SSH private keys, Terraform state, and recovery archives must
remain outside Git. The local `recovery/` directory holds ignored copies needed
by the operator; review `git status` before every commit.

The [recovery schema and validator](recovery/README.md) describe every supported
input, dependency setup, warning policy and exit code. Run the complete offline
check before deployment and review unknown-field warnings without deleting data.
