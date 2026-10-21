# Proxmox and K3s infrastructure

This repository documents the Proxmox VE 9 host and management VM setup, then
provisions a Tailscale subnet router and two three-node K3s clusters.

## Infrastructure at a glance

| Component | VM IDs | Addresses |
| --- | --- | --- |
| Proxmox gateway | — | `192.168.77.1` |
| Management | 200 | `192.168.77.200` |
| Tailscale router | 250 | `192.168.77.250` |
| Dev/stage K3s | 201–203 | `192.168.77.201–203`; API VIP `192.168.77.11` |
| Prod K3s | 211–213 | `192.168.77.211–213`; API VIP `192.168.77.12` |

Each K3s cluster has three server nodes with embedded etcd. The Debian 13
Cloud-Init template is VM `9013`.

## Start here

- [New installation](00-Installation_from-0.md)
- [Infrastructure disaster recovery](01-Disaster_recovery.md)

Both navigators link to the step-specific instructions in `runbooks/`.
For the implemented topology and component boundaries, see
[Current architecture](docs/ARCHITECTURE.md).

## Repository layout

```text
edge/tailscale/                 Tailscale VM and router configuration
edge/nftables/                 Proxmox host DNAT examples
infrastructure/k3s-cluster/    Terraform VMs and Ansible K3s installation
runbooks/                      Operator instructions
recovery/                      Credential examples and local, ignored secrets
scripts/proxmox/               Proxmox host scripts
```

## Keep credentials and state outside Git

Real credentials, SSH private keys, Terraform state, and recovery archives must
remain outside Git. The local `recovery/` directory holds ignored copies needed
by the operator; review `git status` before every commit.
