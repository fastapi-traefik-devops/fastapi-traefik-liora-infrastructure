# Disaster recovery

**Where:** Trusted administrator workstation, then replacement VM 200.
**Data rule:** Preserve recovery sources. Do not replace data restoration with empty initialization.

## 1. Contain and select scope

- [ ] Identify failed infrastructure and protect any surviving hosts, PVCs and archives from deletion.
- [ ] Block conflicting application promotion, Jenkins scheduling and Argo reconciliation.
- [ ] Record incident start, selected infrastructure revision, application digest pairs and recovery targets.
- [ ] Obtain provider console access and the replacement host's current public IPv4.
- [ ] [Prepare recovery inputs](runbooks/10-prepare-recovery-inputs.md).

## 2. Select recovery artifacts

| Component | Recovery source | Handling |
| --- | --- | --- |
| Proxmox/VM/network configuration | Git, module state and private provider inputs | Rebuild/reconcile per module; review plans before apply. |
| Application rows and schema | R2 physical base backup plus WAL for the environment | Select an explicit recovery target; keep writes blocked until restored application checks pass. |
| Application/database credentials and signing keys | Matching protected recovery inputs | Restore matching identities before consumers start; do not generate replacement values silently. |
| K3s datastore | Matching etcd snapshot and original server token, when selecting datastore recovery | Keep this route separate from a fresh control-plane bootstrap. |
| Jenkins | Complete stopped-controller home archive and mounted configuration | Preserve administrator, credential encryption material, jobs and retained history. |
| Monitoring/GitOps/dashboard configuration | Git plus private platform credentials | Recreate configuration and access; preserve surviving metric PVCs. |
| Public TLS | DNS API credential and issuer configuration | Reissue through cert-manager; verify the served certificate. |
| Coordinator | Git source/units, private access profile and retained cycle state | Reprovision cluster-bound identities as needed; inspect the global fence before scheduling. |

- [ ] Match each artifact to its environment, revision, timestamp and checksum.
- [ ] Work from copies; retain original archives and state.
- [ ] Record the physical backup ID, UTC target, source archive identity, post-recovery archive identity and matching Jenkins deployment configuration.

## 3. Rebuild the infrastructure

- [ ] [Check Proxmox](runbooks/00-check-proxmox-9.md) and [recreate the VNet](runbooks/01-create-private-vnet.md).
- [ ] [Restore the existing SSH identity](runbooks/02-prepare-ssh-identity.md); do not regenerate it as an incidental rebuild action.
- [ ] [Recreate template 9013](runbooks/03-create-debian13-template.md), [VM 200](runbooks/04-create-management-vm-200.md) and its [SSH access](runbooks/05-configure-vm200-ssh-dnat.md).
- [ ] [Restore the management checkout/private inputs](runbooks/06-bootstrap-management-checkout.md), [tools](runbooks/11-install-management-tools.md) and [Proxmox API access](runbooks/12-create-proxmox-api-token.md).
- [ ] Reconcile recovered Terraform state against the replacement host before creating resources. Preserve Cloudflare state independently of replaced Proxmox resources.
- [ ] [Restore Tailscale access](runbooks/07-tailscale-private-access.md).
- [ ] [Provision cluster VMs](runbooks/08-provision-cluster-vms.md).
- [ ] For the fresh-control-plane route, [install K3s](runbooks/09-install-k3s-clusters.md). For datastore recovery, use the matching snapshot/token procedure instead; do not mix the two routes.

## 4. Prepare recovery dependencies without starting the application

- [ ] Create the environment namespaces on their assigned clusters. Restore application/database/registry credentials from matching private inputs; keep namespace and role identities unchanged.
- [ ] Provision `cnpg-app` and `cnpg-superuser` from those restored values before creating recovery Clusters. Physical recovery retains database role passwords; match them to the selected recovery point.
- [ ] Install CNPG, cert-manager and Barman using runbooks [18](runbooks/18-cloudnative-pg.md#1-install-the-operator) and [19](runbooks/19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access).
- [ ] Restore R2 access. Confirm the selected physical backup, source archive identity and required WAL.
- [ ] Keep application reconciliation and prestart initialization held. Do not apply the fresh `initdb` Cluster as a substitute for a recovery bootstrap.
- [ ] Restore edge/DNS/issuers using [runbook 15](runbooks/15-publish-application.md). Change only the three application hostnames and their challenge records.

## 5. Restore application data and state

- [ ] Render the environment's Cluster from its overlay without applying the fresh database group.
- [ ] Keep Cluster name `liora-db`, database image/storage/resources and environment instance count; remove `bootstrap.initdb` and the source-archive WAL archiver entry from the recovery manifest.
- [ ] Create a separate `source-archive` ObjectStore referencing the original environment destination and R2 Secret; omit its `retentionPolicy`.
- [ ] Add an `externalClusters` source using `barman-cloud.cloudnative-pg.io`, `barmanObjectName: source-archive` and the original archive `serverName`.
- [ ] Set `bootstrap.recovery.source` to that external source and `recoveryTarget.backupID` / `targetTime` to the selected physical backup ID and UTC target.
- [ ] Apply the read-source ObjectStore before the recovery Cluster. Wait for Cluster Ready and every requested instance before applying application workloads.
- [ ] Keep restore reads isolated from source archive writing/retention. Configure a distinct post-recovery archive server identity and record it in Git, recovery inputs and the coordinator/monitoring recovery record before enabling new archiving. Preserve the source archive for further recovery.
- [ ] Require database readiness, owner `app_owner`, database `app`, expected extensions and migration state.
- [ ] Reconcile the stable `db:5432` Service selector with `cnpg.io/cluster: liora-db` and `role: primary`; confirm its endpoints resolve to the restored primary.
- [ ] Commit the recovery-bootstrap and archive configuration to the environment GitOps definition before releasing Argo self-healing. Require a diff with no database replacement, empty initialization or source-archive writer.
- [ ] Deploy the preserved frontend/backend digest pair. Run only the migration/initialization actions compatible with the restored schema and selected images.
- [ ] Verify existing administrator login and recovered business data; perform and remove a disposable CRUD item.
- [ ] Verify private-edge HTTPS, then canonical public access from an external browser.

**Stop:** Do not use `scripts/backups/pitr.py` to perform live recovery. It is an isolated exercise that creates disposable markers/resources and removes them. Keep the application held if the selected recovery target, required WAL or matching credentials are missing.

## 6. Restore platform state

- [ ] Recover Jenkins using the [controller state checklist](runbooks/17-migrate-jenkins-ci.md#6-controller-backup-and-recovery-checklist) and the matching home/configuration archive. Start under an execution hold.
- [ ] Verify administrator access, credential decryption, retained users/jobs/history and pinned helpers before allowing builds.
- [ ] Recreate monitoring and private access using [runbook 16](runbooks/16-private-platform-access.md); restore private Grafana and Slack credentials.
- [ ] Restore GitOps roots/children using [runbook 14](runbooks/14-install-argocd.md), with automation disabled until resource diffs match the recovery state.
- [ ] Reinstall the VM 250 coordinator from [runbook 19](runbooks/19-cnpg-r2-backup-pitr.md#2-install-the-coordinator-on-vm-250). Inspect retained intent before enabling a schedule.

## 7. Release operation

- [ ] Require source/running image agreement, recovered data checks, HTTPS/login/CRUD and correct Argo ownership.
- [ ] Require PROD standby placement and asynchronous streaming health.
- [ ] Verify WAL archiving to the selected post-recovery destination and a coordinated base-backup cycle.
- [ ] Restore child Argo policies before roots and restore the recorded Jenkins allowlist/triggers.
- [ ] Restore the single VM 250 timer only after its fence/state is understood.
- [ ] Record recovery time, recovered point, data loss, retained evidence and release decision in the incident record.

**Done when:** Recovered data and platform identities are usable, application checks pass, backup protection is restored, and only approved automation has resumed.
