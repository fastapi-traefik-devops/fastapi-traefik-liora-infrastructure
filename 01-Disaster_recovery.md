# Disaster recovery

**Where:** Trusted administrator laptop, then replacement VM 200.
**Data rule:** Preserve recovery sources. Do not replace data restoration with empty initialization.

**Resume after an interruption:** Find the last completed checkbox, then read
the next linked procedure from its preflight. Compare its completion checks
with live state before continuing. Do not rerun provisioning, initialization
or deletion commands just because a previous operator checked a box.

## 1. Contain and select scope

- [ ] Use a trusted laptop with Internet access and an infrastructure
      repository checkout.
- [ ] Obtain root SSH or console access to the preconfigured replacement
      Proxmox host. Record its current public IPv4 address. Step 1 below
      checks the Proxmox version and upgrades it if necessary.
- [ ] Obtain the encrypted credentials archive and its separately stored
      password. Keep the source archive and password separate.
- [ ] [Unpack the credentials ZIP](runbooks/25-unpack-credentials-zip.md)
      into the laptop checkout's ignored `recovery/` directory.
- [ ] Identify failed infrastructure and protect any surviving hosts, PVCs and archives from deletion.
- [ ] [Hold automation on surviving clusters](runbooks/24-hold-surviving-automation.md).
      Record each component that is unreachable.
- [ ] Record incident start, selected infrastructure revision, application digest pairs and recovery targets.
- [ ] Identify the selected repository revision, Terraform state, and backup
      set before changing the replacement host.
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

### Steps 1–6 — Work from your workstation

The replacement VM 200 does not exist yet. Use the provider console or root
access to the replacement Proxmox host.

1. **Confirm the replacement host.** Require Proxmox VE 9 and nftables before
   recreating private networking or host NAT.
   - [ ] [Check Proxmox VE 9](runbooks/00-check-proxmox-9.md).
2. **Recreate the private network.** Keep `vnet77`,
   `192.168.77.0/24` and gateway `192.168.77.1` so restored VM addresses match.
   - [ ] [Create the private VNet](runbooks/01-create-private-vnet.md).
3. **Restore the administrator SSH identity.** Reuse the existing key pair
   from the recovery archive; do not generate a different identity as part of
   the rebuild.
   - [ ] [Prepare the existing SSH key](runbooks/02-prepare-ssh-identity.md).
4. **Recreate the Debian 13 template.** VM `9013` is the source for the
   management and cluster VMs; choose storage available on the replacement host.
   - [ ] [Create template 9013](runbooks/03-create-debian13-template.md).
5. **Recreate the management VM.** Clone the template to VM `200` at
   `192.168.77.200` with the restored administrator public key.
   - [ ] [Create VM 200](runbooks/04-create-management-vm-200.md).
6. **Restore the SSH entry point.** Forward public TCP `22200` to
   `192.168.77.200:22`; the replacement host's public IP may differ.
   - [ ] [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

### Continue on management VM 200

> [!IMPORTANT]
> Run the remaining infrastructure commands from VM 200. Use your workstation
> as the SSH client; a linked procedure identifies any checks that run elsewhere.

7. **Restore the control machine.** Connect to VM `200`. Clone infrastructure
   into `~/fastapi-traefik-liora-infrastructure`, select the recorded revision,
   and transfer the ignored `recovery/` files from the laptop.
   - [ ] [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md).
8. **Install the operator tools.** VM `200` needs Ansible, Terraform and
   the tools used to inspect both Kubernetes clusters.
   - [ ] [Install management tools](runbooks/11-install-management-tools.md).
9. **Restore Proxmox API access.** Use a valid token for the replacement host
   before any Terraform plan or apply.
   - [ ] [Create or verify the Proxmox API token](runbooks/12-create-proxmox-api-token.md).
10. **Reconcile infrastructure state.** Compare recovered Terraform state
    with the replacement host before provisioning. Keep Cloudflare state
    separate from Proxmox VM state.
    - [ ] [Inspect router state and VM 250](runbooks/07-tailscale-private-access.md#if-restoring-terraform-state).
    - [ ] [Inspect cluster VM state and existing IDs](runbooks/08-provision-cluster-vms.md#initialize-terraform-and-reconcile-state).
11. **Restore private access.** Recreate VM `250` and reapprove the
    `192.168.77.0/24` subnet route when required.
    - [ ] [Provision the Tailscale router](runbooks/07-tailscale-private-access.md).
12. **Restore the cluster VMs.** Reconcile or create VMs `201–203` and
    `211–213` without replacing surviving data by accident.
    - [ ] [Provision both VM groups](runbooks/08-provision-cluster-vms.md).
13. **Build the control planes.** The standard recovery route creates fresh
    K3s clusters, deploys platform/configuration and restores application data.
    - [ ] [Install both K3s clusters](runbooks/09-install-k3s-clusters.md).

Etcd snapshots are also retained in R2. [Runbook 21](runbooks/21-restore-k3s-etcd-snapshot.md)
is an optional manual datastore-recovery route, outside this sequence. It uses
the selected snapshot's original token and does not restore PVC contents.

## 4. Prepare recovery dependencies without starting the application

**Where:** VM 200 for Kubernetes commands; use the protected recovery kit for
secrets and backup selection. Keep application writes, prestart and Argo
automation held throughout this section.

14. **Re-establish operator dependencies.** Use explicit kubeconfigs for both
    clusters and the recovered credentials for each environment.
    - [ ] [Prepare the operator tools](runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
    - [ ] [Validate the recovered private inputs](recovery/README.md#recovery-inputs-and-validation).
15. **Install platform operators.** CNPG, cert-manager and Barman must exist
    before recovery custom resources are applied; no empty database is created.
    - [ ] [Install CNPG in both clusters](runbooks/18-cloudnative-pg.md#1-install-the-operator).
    - [ ] [Install cert-manager and Barman only](runbooks/19-cnpg-r2-backup-pitr.md#install-platform-operators-in-either-scenario).
16. **Prepare the original database identities.** Restore the matching
    application, registry, R2 and database credentials. Keep the original
    `app_owner` and `postgres` passwords associated with the selected backup.
    - [ ] [Match the backup and credential inputs](runbooks/10-prepare-recovery-inputs.md#select-the-recovery-route).
17. **Restore the edge prerequisites.** Use the replacement public IP for the
    application DNS records; prepare the edge and issuers without serving an
    unverified application.
    - [ ] [Provision edge VM 240](runbooks/15-publish-application.md#1-inspect-and-provision-the-edge).
    - [ ] [Update only the application DNS records](runbooks/15-publish-application.md#2-dns-and-certificate-prerequisites).
    - [ ] [Provision certificate issuers](runbooks/15-publish-application.md#3-provision-cluster-local-certificate-management).

## 5. Restore application data and state

- [ ] Restore DEV data and confirm its selected recovery point:
      [live PostgreSQL restore](runbooks/20-restore-live-postgresql.md).
- [ ] Restore STAGE data and confirm its selected recovery point:
      [live PostgreSQL restore](runbooks/20-restore-live-postgresql.md).
- [ ] Restore PROD data and confirm its selected recovery point:
      [live PostgreSQL restore](runbooks/20-restore-live-postgresql.md).
- [ ] After each restore, check the preserved frontend/backend image pair,
      recovered data and login. Issue its `app-tls` certificate, publish its
      edge route, then check HTTPS through the canonical hostname using
      [runbook 15, sections 4–6](runbooks/15-publish-application.md#4-issue-monitor-and-renew-application-certificates).

## 6. Restore platform state

Continue here only after the restored application passes the checks in section 5.
Keep Jenkins scheduling and GitOps automation disabled while comparing state.

18. **Restore private administration and monitoring.** Use the recovered
    Grafana and notification credentials on the correct cluster.
    - [ ] [Configure Admin VIPs and monitoring](runbooks/16-private-platform-access.md).
19. **Restore Jenkins state.** Match the stopped controller-home archive with
    its mounted configuration. Start under an execution hold and verify users,
    history and credential decryption before allowing builds.
    - [ ] [Restore the Jenkins controller home](runbooks/23-restore-jenkins-controller.md).
    - [ ] [Check restored jobs, credentials and observer gate](runbooks/27-configure-jenkins-jobs.md).
20. **Restore GitOps ownership.** Compare child and root Application diffs
    against the recovered database and application revision before automation.
    - [ ] [Install Argo CD and reconcile resources](runbooks/14-install-argocd.md).
21. **Restore backup coordination.** Reinstall on VM `250`; inspect retained
    cycle intent and the global fence before enabling the timer.
    - [ ] [Preserve and replace cluster-bound coordinator access](runbooks/26-rebuild-backup-coordinator-access.md).
    - [ ] [Install and inspect the coordinator without a cycle](runbooks/19-cnpg-r2-backup-pitr.md#install-without-starting-a-cycle).
    - [ ] [Configure independent native etcd backups](docs/operations/ETCD_BACKUPS.md#configure-or-reapply-native-backups).

## 7. Release operation

22. **Prove the recovered service.** Confirm source/running image agreement,
    recovered data, HTTPS/login/CRUD and correct Argo ownership on all three
    environments; require PROD standby placement and asynchronous replication.
    - [ ] [Check application access](runbooks/13-deploy-application-manifests.md#5-check-application-access).
    - [ ] [Check PROD database replication](runbooks/18-cloudnative-pg.md#4-verify-database-and-application).
23. **Prove backup protection.** Check WAL archiving to the new destination
    and a completed coordinated base-backup cycle before restoring schedules.
    - [ ] [Run and inspect the backup coordinator](runbooks/19-cnpg-r2-backup-pitr.md#run-a-cycle-after-database-acceptance).
24. **Release automation deliberately.** Restore child Argo policies before
    roots, the recorded Jenkins allowlist/triggers and the single VM `250`
    timer only after its retained state is understood.
    - [ ] [Review Argo automation](runbooks/14-install-argocd.md#4-adopt-manually-then-review-automation).
    - [ ] [Activate approved Jenkins delivery](runbooks/17-install-operate-jenkins.md#4-activate-delivery).
    - [ ] [Enable the backup timer](runbooks/19-cnpg-r2-backup-pitr.md#enable-the-timer-after-reviewing-retained-state).
25. **Record the recovery result.** Record recovery time, recovered point,
    data loss, retained evidence and release decision in the incident record.

**Done when:** Recovered data and platform identities are usable, application checks pass, backup protection is restored, and only approved automation has resumed.
