# Fresh deployment

**Result:** Infrastructure, platform services and application environments with empty databases.
**Data rule:** Do not restore application rows or Jenkins history on this route.

## 1. Prepare the operator and host

**Where:** Trusted administrator workstation and Proxmox console.

- [ ] Obtain provider console/root access and record the current public IPv4 address.
- [ ] Prepare the reviewed repository revision and protected credential storage.
- [ ] [Check Proxmox VE 9](runbooks/00-check-proxmox-9.md).
- [ ] [Create the private VNet](runbooks/01-create-private-vnet.md).
- [ ] [Prepare the administrator SSH identity](runbooks/02-prepare-ssh-identity.md).
- [ ] [Create Debian template 9013](runbooks/03-create-debian13-template.md).
- [ ] [Create VM 200](runbooks/04-create-management-vm-200.md).
- [ ] [Configure its SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

## 2. Build management access and clusters

**Where:** VM 200, repository root unless the linked procedure says otherwise.

- [ ] [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md).
- [ ] [Install management tools](runbooks/11-install-management-tools.md).
- [ ] [Configure Proxmox API access](runbooks/12-create-proxmox-api-token.md).
- [ ] Prepare private recovery inputs using the [schema](recovery/README.md).
- [ ] [Provision Tailscale VM 250 and approve the subnet route](runbooks/07-tailscale-private-access.md).
- [ ] [Provision cluster VMs](runbooks/08-provision-cluster-vms.md).
- [ ] [Install both K3s clusters](runbooks/09-install-k3s-clusters.md).

## 3. Prepare platform dependencies

- [ ] Prepare the operator Python/browser tools using the [workspace guide](runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
- [ ] Create `app-dev` and `app-stage` namespaces on NONPROD and `app-prod` on PROD using [runbook 13, section 2](runbooks/13-deploy-application-manifests.md#2-prepare-namespace-credentials-and-storage).
- [ ] Install the CNPG operator in both clusters using [runbook 18, section 1](runbooks/18-cloudnative-pg.md#1-install-the-operator). Do not create database Clusters yet.
- [ ] Install cert-manager/Barman and provision R2 access using [runbook 19, section 1](runbooks/19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access).
- [ ] Provision VM 240, application DNS and certificate issuers using [runbook 15, sections 1–3](runbooks/15-publish-application.md#1-inspect-and-provision-the-edge).

## 4. Initialize application environments

- [ ] Deploy DEV using [runbook 13](runbooks/13-deploy-application-manifests.md): private inputs → CNPG credentials → empty database → prestart/Alembic → application workloads.
- [ ] Complete certificate issuance, edge configuration and HTTPS serving using [runbook 15](runbooks/15-publish-application.md).
- [ ] Require DEV login and disposable create/read/update/delete.
- [ ] Repeat for STAGE, then PROD, preserving environment separation and the selected image digest pairs.
- [ ] Require two PROD database instances on different nodes with asynchronous streaming replication.

## 5. Establish continuous operation

- [ ] [Install Argo CD and adopt the environment resources](runbooks/14-install-argocd.md), NONPROD before PROD.
- [ ] [Configure private Admin VIPs and monitoring](runbooks/16-private-platform-access.md).
- [ ] [Install Jenkins](runbooks/17-migrate-jenkins-ci.md) using a fresh controller home and reviewed job/agent configuration.
- [ ] [Install the VM 250 backup coordinator](runbooks/19-cnpg-r2-backup-pitr.md#2-install-the-coordinator-on-vm-250).
- [ ] Run the first coordinated full backups. Complete [separate backup verification](docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md), then enable the sole daily timer.
- [ ] Confirm notification routing and FIRING/RESOLVED delivery using [Slack operations](docs/operations/SLACK_ALERTING.md).
- [ ] Place credentials, state and required controller configuration in the protected off-host recovery kit.

**Done when:** All three applications pass HTTPS/login/CRUD, Argo ownership is correct, private interfaces work, backups/PITR complete, and only approved CI/deployment automation is active.
