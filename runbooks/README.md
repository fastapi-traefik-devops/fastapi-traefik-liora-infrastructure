# Operator procedures

## Choose a scenario

| Scenario | Start here | Data rule |
| --- | --- | --- |
| Fresh deployment | [Installation checklist](../00-Installation_from-0.md) | Initialize empty databases; do not import application data. |
| Disaster recovery | [Recovery checklist](../01-Disaster_recovery.md) | Restore matching data, credentials and configuration before resuming writes. |
| Routine backup/recovery operations | [Backup operations](19-cnpg-r2-backup-pitr.md) | Preserve live endpoints; use guarded isolated exercises. |

## Procedure map

| Procedure | Purpose |
| --- | --- |
| [00](00-check-proxmox-9.md)–[06](06-bootstrap-management-checkout.md) | Host, network, administrator access and management checkout |
| [07](07-tailscale-private-access.md) | Tailscale VM 250 and private subnet route |
| [08](08-provision-cluster-vms.md)–[09](09-install-k3s-clusters.md) | Cluster VMs and K3s |
| [10](10-prepare-recovery-inputs.md) | Recovery artifact selection |
| [11](11-install-management-tools.md)–[12](12-create-proxmox-api-token.md) | Management tools and Proxmox access |
| [13](13-deploy-application-manifests.md) | Fresh application initialization and checks |
| [14](14-install-argocd.md) | Independent Argo CD installation and resource adoption |
| [15](15-publish-application.md) | Edge, DNS and public certificate lifecycle |
| [16](16-private-platform-access.md) | Private interfaces and monitoring |
| [17](17-migrate-jenkins-ci.md) | Jenkins installation, operation and state preservation |
| [18](18-cloudnative-pg.md) | Fresh CNPG database installation and maintenance |
| [19](19-cnpg-r2-backup-pitr.md) | R2 backup setup and cycle recovery |

## Operating rules

- Check **Where**, target cluster/environment and prerequisites before commands.
- Perform checkboxes in order. Stop at a failed gate; do not skip ahead.
- Use explicit kubeconfigs. Keep NONPROD and PROD identities separate.
- Preserve data-bearing resources and private inputs unless the selected procedure explicitly identifies them for removal.
- Keep credential values, state and raw sensitive diagnostics outside Git.
- Record change/incident results separately from the manual.

Architecture: [desired system](../docs/ARCHITECTURE.md).
Inputs: [recovery schema](../recovery/README.md).
Monitoring: [Slack](../docs/operations/SLACK_ALERTING.md),
[Grafana](../docs/operations/GRAFANA_OPERATIONS_DASHBOARDS.md),
[storage/replication](../docs/operations/STORAGE_REPLICATION_ALERTS.md).
Implementation history and capability status: [phase reports](../docs/testreports/README.md).

Backup verification exercises: [isolated PITR and WAL delivery](../docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md).
