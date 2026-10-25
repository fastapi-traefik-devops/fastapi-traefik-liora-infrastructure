# Fresh deployment

**Result:** Infrastructure, platform services, and application environments
with empty databases.
**Data rule:** Do not restore application rows or Jenkins history on this route.

**Resume after an interruption:** Find the last checked action below. Open the
next linked runbook, repeat its read-only preflight against the actual host or
cluster, and continue only when its completion checks pass. A checked box is a
record of a completed check, not permission to rerun a provisioning command.

## Before you start

- [ ] Use a trusted laptop with Internet access and an infrastructure
      repository checkout. Record the Proxmox public IPv4 address.
- [ ] Confirm root SSH or console access to the preconfigured Proxmox host.
      The host can run an older Proxmox version; step 1 checks and upgrades it.
- [ ] Obtain the encrypted credentials archive and its separately stored
      password. Keep the archive and password separate.
- [ ] [Unpack the credentials ZIP](runbooks/25-unpack-credentials-zip.md)
      into the laptop checkout's ignored `recovery/` directory.
- [ ] Confirm the archive contains the administrator SSH key pair and the
      credentials required for this deployment. See
      [recovery inputs](recovery/README.md).

## 1. Prepare Proxmox from your workstation

**Where:** Trusted administrator workstation and Proxmox console. VM 200 does
not exist yet.

1. **Confirm the host baseline.** Proxmox VE 9 and nftables are required
   before configuring the private network and host NAT.
   - [ ] [Check Proxmox VE 9](runbooks/00-check-proxmox-9.md).
2. **Create the private network.** `vnet77` carries the
   `192.168.77.0/24` VM network; Proxmox is its gateway at `192.168.77.1`.
   - [ ] [Create and verify the private VNet](runbooks/01-create-private-vnet.md).
3. **Prepare the administrator SSH identity.** Use the key pair from the
   credentials archive. Copy its public key to Proxmox for VM 200 Cloud-Init.
   - [ ] [Prepare the SSH key pair](runbooks/02-prepare-ssh-identity.md).
4. **Create the Debian 13 template.** VM `9013` is the clone source; select
   the host's actual VM disk storage before running the creation script.
   - [ ] [Create template 9013](runbooks/03-create-debian13-template.md).
5. **Create the management VM.** Clone VM `9013` into VM `200` at
   `192.168.77.200`; subsequent infrastructure work runs from this VM.
   - [ ] [Create VM 200](runbooks/04-create-management-vm-200.md).
6. **Open the initial SSH path.** Forward public TCP `22200` to VM 200's
   port `22` so the workstation can reach the private VM.
   - [ ] [Configure VM 200 SSH DNAT](runbooks/05-configure-vm200-ssh-dnat.md).

## 2. Build management access and clusters

> [!IMPORTANT]
> After step 6, run infrastructure commands from VM 200. Use your workstation
> as the SSH client; a linked procedure identifies any checks that run elsewhere.

**Where:** VM 200, repository root unless the linked procedure says otherwise.

7. **Prepare the control machine.** Connect to VM `200` through the new SSH
   path. Clone infrastructure into `~/fastapi-traefik-liora-infrastructure`
   and transfer the ignored `recovery/` files from the laptop.
   - [ ] [Bootstrap the management checkout](runbooks/06-bootstrap-management-checkout.md).
8. **Install the operator tools.** Ansible configures the guests, Terraform
   provisions VMs, and kubectl/Helm manage cluster resources.
   - [ ] [Install Ansible, Terraform, kubectl and Helm](runbooks/11-install-management-tools.md).
9. **Enable Proxmox automation.** Add the current host's API token to the
   transferred `recovery/.env`. Terraform uses it to read template `9013`
   and provision VMs.
   - [ ] [Create and verify Proxmox API access](runbooks/12-create-proxmox-api-token.md).
10. **Check private inputs.** Check the transferred SSH identity, registry
    credentials, and application credentials before provisioning.
    - [ ] [Validate the recovery input files](recovery/README.md#recovery-inputs-and-validation).
11. **Establish private access.** VM `250` advertises `192.168.77.0/24`
    through Tailscale; approve the subnet route before relying on VPN access.
    - [ ] [Provision the Tailscale router](runbooks/07-tailscale-private-access.md).
12. **Create both cluster VM groups.** DEV/STAGE uses VMs `201–203`;
    PROD uses `211–213`, all cloned from template `9013`.
    - [ ] [Provision the cluster VMs](runbooks/08-provision-cluster-vms.md).
13. **Install two independent K3s clusters.** Keep inventories, API VIPs,
    server tokens and kubeconfigs separate for NONPROD and PROD.
    - [ ] [Install and verify both clusters](runbooks/09-install-k3s-clusters.md).

## 3. Prepare platform dependencies

**Where:** VM 200 for commands; use the linked runbook when a check must run
from a browser or another host. Keep NONPROD and PROD kubeconfigs explicit.

14. **Prepare local deployment tools.** The application and backup helpers use
    the pinned Python environment and browser tools.
    - [ ] [Install the operator Python/browser tools](runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
15. **Create the three application namespaces.** DEV and STAGE live on
    NONPROD; PROD lives on the other cluster. Do not initialize a database yet.
    - [ ] [Select DEV and create its namespace](runbooks/13-deploy-application-manifests.md#create-the-selected-namespace).
    - [ ] [Select STAGE and create its namespace](runbooks/13-deploy-application-manifests.md#create-the-selected-namespace).
    - [ ] [Select PROD and create its namespace](runbooks/13-deploy-application-manifests.md#create-the-selected-namespace).
16. **Install database and backup operators.** Both clusters need CNPG,
    cert-manager and the Barman plugin before database custom resources exist.
    - [ ] [Install CNPG in both clusters](runbooks/18-cloudnative-pg.md#1-install-the-operator).
    - [ ] [Install cert-manager/Barman and provision R2 access](runbooks/19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access).
17. **Prepare public application routing.** Provision edge VM `240`, the
    three application DNS records and certificate issuers. Certificates are
    issued after each application overlay is applied.
    - [ ] [Provision edge VM 240](runbooks/15-publish-application.md#1-inspect-and-provision-the-edge).
    - [ ] [Prepare application DNS](runbooks/15-publish-application.md#2-dns-and-certificate-prerequisites).
    - [ ] [Provision certificate issuers](runbooks/15-publish-application.md#3-provision-cluster-local-certificate-management).

## 4. Initialize application environments

**Where:** VM 200 for Kubernetes commands; use a browser for the final access
checks. Complete one environment before starting the next: DEV → STAGE → PROD.

18. **Initialize DEV with empty data.** Use the selected image digest pair;
    create its credentials, CNPG Cluster, prestart Job and application workloads in
    that order. Stop after workload startup; HTTPS checks follow in step 19.
    - [ ] [Deploy DEV through workload startup](runbooks/13-deploy-application-manifests.md#1-select-and-render-one-environment).
19. **Serve DEV over HTTPS.** Finish certificate issuance and edge routing,
    then check the canonical public hostname, login and a disposable CRUD item.
    - [ ] [Issue DEV's certificate](runbooks/15-publish-application.md#4-issue-monitor-and-renew-application-certificates).
    - [ ] [Publish HTTPS through the edge](runbooks/15-publish-application.md#5-align-https-configuration-and-publish-443).
    - [ ] [Check application access](runbooks/13-deploy-application-manifests.md#5-check-application-access).
20. **Repeat for STAGE and PROD.** Re-select the environment and kubeconfig
    each time; never reuse DEV's namespace or image identifiers by assumption.
    - [ ] [Deploy STAGE through workload startup](runbooks/13-deploy-application-manifests.md#1-select-and-render-one-environment).
    - [ ] [Issue STAGE's certificate](runbooks/15-publish-application.md#4-issue-monitor-and-renew-application-certificates).
    - [ ] [Publish STAGE HTTPS](runbooks/15-publish-application.md#5-align-https-configuration-and-publish-443).
    - [ ] [Verify STAGE login and CRUD](runbooks/13-deploy-application-manifests.md#5-check-application-access).
    - [ ] [Deploy PROD through workload startup](runbooks/13-deploy-application-manifests.md#1-select-and-render-one-environment).
    - [ ] [Issue PROD's certificate](runbooks/15-publish-application.md#4-issue-monitor-and-renew-application-certificates).
    - [ ] [Publish PROD HTTPS](runbooks/15-publish-application.md#5-align-https-configuration-and-publish-443).
    - [ ] [Verify PROD login and CRUD](runbooks/13-deploy-application-manifests.md#5-check-application-access).
    - [ ] [Check PROD instances and asynchronous replication](runbooks/18-cloudnative-pg.md#4-verify-database-and-application).

## 5. Establish continuous operation

**Where:** VM 200 for installation and checks, except where a linked procedure
specifies VM 250 or a private browser session.

21. **Hand ownership to GitOps.** Install Argo CD independently on NONPROD
    and PROD; compare each resource before enabling reconciliation.
    - [ ] [Install Argo CD and adopt the environments](runbooks/14-install-argocd.md).
22. **Open private platform access.** Configure Admin VIPs and monitoring;
    keep these interfaces off public application routing.
    - [ ] [Configure private access and monitoring](runbooks/16-private-platform-access.md).
23. **Install fresh CI.** Create a new Jenkins controller home. Review the
    controller, agents, credentials, and job policy before enabling builds.
    - [ ] [Install the Jenkins controller](runbooks/17-migrate-jenkins-ci.md#1-install-a-fresh-controller).
    - [ ] [Install agents for the fresh controller](runbooks/22-install-fresh-jenkins-agents.md).
    - [ ] [Configure and check delivery](runbooks/17-migrate-jenkins-ci.md#2-configure-delivery-identities).

24. **Protect the databases.** Install the coordinator on VM `250`, run the
    first sequential backup cycle and verify an isolated restore before
    enabling its sole daily timer.
    - [ ] [Install the coordinator and run a cycle](runbooks/19-cnpg-r2-backup-pitr.md#2-install-the-coordinator-on-vm-250).
    - [ ] [Verify backup recovery](docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md).
25. **Check operational handoff.** Confirm alert delivery and store the
    protected credentials, Terraform state and Jenkins configuration off-host.
    - [ ] [Verify FIRING and RESOLVED notifications](docs/operations/SLACK_ALERTING.md).
    - [ ] [Check recovery-kit contents](recovery/README.md#recovery-kit-checklist).

**Done when:** All three applications pass HTTPS/login/CRUD, Argo ownership is correct, private interfaces work, backups/PITR complete, and only approved CI/deployment automation is active.
