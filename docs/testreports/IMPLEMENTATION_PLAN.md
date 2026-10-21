# Kubernetes implementation plan

## Target architecture

The final state uses two independent K3s clusters and three application
environments. DEV and STAGE share one cluster but have separate namespaces and
data. PROD runs on its own cluster.

| Component | Dev/stage cluster | Prod cluster |
| --- | --- | --- |
| K3s | VMs 201–203; API VIP `192.168.77.11` | VMs 211–213; API VIP `192.168.77.12` |
| Application | `app-dev` and `app-stage` namespaces | `app-prod` namespace |
| GitOps | Own Argo CD, AppProject, and root Application | Independent Argo CD, AppProject, and root Application |
| Sync | Reviewed PR, then auto-sync, self-heal, and reviewed pruning | Reviewed PR, then auto-sync and self-heal; no automatic pruning |
| Secrets | Cluster-specific Sealed Secrets key; GHCR pull credentials per namespace | Separate controller key and GHCR pull credentials |
| Data | Separate DEV and STAGE databases | PROD database with tested backups and restore |
| Monitoring | Cluster monitoring and administrative Grafana | Separate monitoring and controlled access to PROD metrics |

The planned public path is Cloudflare → Proxmox TCP/443 DNAT → dedicated
HAProxy edge VM → the selected cluster's Traefik ingress → application Service.
Each cluster needs an ingress address distinct from its API VIP. Argo CD,
Grafana, Prometheus, Adminer while retained, and other administrative
interfaces are reached through Tailscale or another controlled private path.

The target database platform is CloudNativePG. The initial deployment below
deliberately retains the application's current PostgreSQL Deployment and PVC;
database migration is a later, separately verified change. Likewise, the
current Ansible configures kube-vip only for the API and leaves K3s ServiceLB
enabled. The ingress design must account for that before implementing public
routing. The application's current Phase 1 Jenkins runs on a separate Docker
host; its eventual placement is a separate CI decision.

### Target repository layout

```text
docs/testreports/           Plans and phase reports
kubernetes/
  apps/liora/
    base/
    overlays/dev/
    overlays/stage/
    overlays/prod/
  gitops/argocd/
    nonprod/                 root app, project, DEV/STAGE apps, bootstrap
    prod/                    independent root app, project, PROD app, bootstrap
  platform/
    nonprod/                 cluster services introduced incrementally
    prod/                    independent PROD cluster services
```

The Phase 0 baseline report and migration instructions accompany this plan.
The application base and overlays have been imported with selected history;
see [Phase 1 report](PHASE1_REPORT.md). All three overlays render with real,
pinned images, including the approved PROD pair. DEV, STAGE and PROD are
deployed and privately verified in Phases 3–5, including mutual isolation.
PROD uses one backend worker per Pod with two replicas after its compatibility
fix. The migration is integrated into the original checkout on `main`. Never
commit live credentials, controller private keys, or state.

### Target ownership and source files

- The application repository retains application code, tests, image builds,
  release tags, and the Jenkins pipeline that publishes images. This
  infrastructure repository owns deployed image digests, Kustomize overlays,
  Argo CD configuration, and cluster services.
- The first migration copies `deploy/base/` and
  `deploy/overlays/{dev,stage,prod}/` from the application repository. The
  later CloudNativePG migration replaces `configmap-db.yaml`,
  `deployment-db.yaml`, `service-db.yaml`, and `pvc-db.yaml` in the active
  base. Remove Adminer only after an alternative operational path works.
- Adapt `argocd/app-dev.yaml`, `app-stage.yaml`, and `project.yaml` for
  the nonprod cluster. Create independent PROD equivalents, bootstrap
  resources, and root Applications. Each Argo CD points to this repository
  and deploys to its own cluster via `https://kubernetes.default.svc`.
  The existing `argocd/applicationset.yaml` cannot be copied unchanged:
  it creates all three environments in one cluster.
- Adapt `monitoring/values.yaml`, `kustomization.yaml`,
  `dashboards/platform.yaml`, `monitors/{argocd,traefik}.yaml`, and
  `rules/dev-stage.yaml` when adding monitoring. Replace kind-specific
  storage assumptions and create distinct PROD settings.
- Move promotion to reviewed changes in this repository. Adapt
  `ci/promote.py`, `promote-stage.sh`, `publish.sh`, `registry.py`, and
  `Jenkinsfile.promote` without executing trusted publishing code from an
  untrusted application checkout. Add rendering and placeholder-image checks
  for all three overlays. The GitOps GitHub App needs access to this repository.
- Do not deploy the application's historical `k8s/` tree, old SealedSecret
  ciphertext, or application `.env` files. Review `infra/jenkins-host/`
  separately from the Kubernetes manifests.

## Implementation order

Write all new implementation plans and phase reports in `docs/testreports/`.

First run the application's **current deployment** on the new clusters with the
fewest necessary changes. Verify DEV, STAGE, and PROD independently. Add GitOps,
public access, monitoring, and platform replacements in later, separate steps.
Complete the check for each phase before starting the next.

Copy deployment files from the
[application repository](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application).
It was reviewed at commit `3a610ebb14f265fcdeb5a1d4d59da9fa543648c5`;
record the actual source commit when copying. Its historical `k8s/` tree and
this repository's `examples/kubernetes/` are references, not deployment sources.

## Phase 0 — Establish the baseline

Status on 2026-10-21: **complete, including the storage verification subsequently
performed in Phase 2**. Phase 0 itself was read-only. The operator authorized
Phase 1 before live storage checks, then explicitly authorized Phase 2.
See the [Phase 0 baseline](PHASE0_BASELINE.md) for the original observations and
[Phase 2 report](PHASE2_REPORT.md) for completed namespace, Secret and storage
verification.

- [x] Confirm both K3s contexts work from management VM 200 and all six nodes
      are Ready. Keep the dev/stage and prod contexts distinct.
- [x] Record the source commit, DEV/STAGE image digests, and image digests
      selected for the first PROD deployment.
- [x] Confirm each cluster has a working StorageClass and enough capacity for
      the existing PostgreSQL PVCs and application replicas.
- [x] Locate the credentials needed for `ghcr-pull-secret`, `backend-secrets`,
      and `db-secrets` in each application namespace. Keep live values in the
      external recovery archive, not Git.

Verified: both contexts and all six Ready nodes; all source overlays render;
source/image references and approved PROD digests recorded. Both default
local-path provisioners are Running and reported capacity is sufficient.
Phase 2 created a temporary 1Gi RWO PVC and consumer Pod in each target namespace;
all bound to local-path and passed write/read checks. Probe resources and PVs
were removed. A STAGE runtime interruption passed on retry and is documented
in the Phase 2 report.

Fresh, separate backend/database credentials reside in ignored
`recovery/recovery.yaml`, with registry credentials in ignored `recovery/.env`.
Phase 2 created and verified the corresponding live Secrets in each namespace.
No credential values were committed. Phases 3–5 subsequently deployed and
verified all three application environments.

**Pass:** both clusters, storage, image versions, and credentials are ready.

## Phase 1 — Copy the current application deployment

Status on 2026-10-21: **complete for local import and rendering**. The operator
approved the current STAGE pair for PROD; both images are pinned by digest.
See [Phase 1 report](PHASE1_REPORT.md). Work is isolated
on `migration/liora-phase0` at `/home/root-admin/liora-infrastructure-migration`.
The deployment source is upstream `b98a22e48527c256193ed65c10307eb574b27ab6`;
its newer STAGE promotion matches kind. The selected history was scanned and
imported, and the new runbook and navigator links are present. No live application deployment was attempted.

- [x] Copy **all** of `deploy/base/` to `kubernetes/apps/liora/base/`, including
      PostgreSQL, its PVC and Service, Adminer, the prestart Job, backend,
      frontend, Ingress, and the existing `kustomization.yaml`.
- [x] Copy `deploy/overlays/{dev,stage,prod}/` to matching directories in
      `kubernetes/apps/liora/overlays/`. The Kustomize files are required;
      DEV/STAGE `promotion.json` files are records, not deployment inputs.
- [x] Render all three overlays with explicit-kubeconfig `kubectl kustomize`;
      inspect namespaces, images, replicas, Secret references, and Ingress hosts.
- [x] Replace PROD's `sha-000000...` placeholders with **existing, selected**
      backend and frontend digests. Limit other edits to K3s compatibility
      and the operator-requested domain/administrator configuration.

Operator-requested configuration is now `dev.liora.aprt.info`,
`stage.liora.aprt.info`, and `liora.aprt.info`, with initial administrator
`admin007@liora.aprt.info`. The ignored recovery file uses the same identity.
DEV retains HTTP and its source `ENVIRONMENT: staging`; STAGE/PROD retain
HTTPS and the `app-tls` dependency. PROD uses tag
`sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`, backend digest
`sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d`,
and frontend digest
`sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91`.
No DNS, TLS or public ingress was set up.

**Pass:** three overlays render with real images and the active base retains
the current working stack. Do not copy Argo CD, monitoring, Jenkins, or the
historical `k8s/` tree in this phase.

## Phase 2 — Prepare namespaces and credentials

Status on 2026-10-21: **complete**. See [Phase 2 report](PHASE2_REPORT.md).
Namespaces are Active, all nine required Secrets match local recovery material,
and temporary default-StorageClass PVC probes passed in every namespace. The
probe Pods, PVCs and dynamically provisioned PVs were removed. All six nodes
are Ready. The subsequent DEV deployment is recorded in Phase 3 below.

- [x] Create `app-dev` and `app-stage` on the dev/stage cluster and `app-prod`
      on the prod cluster.
- [x] Restore or create `ghcr-pull-secret`, `backend-secrets`, and `db-secrets`
      in each namespace; ensure backend and database credentials agree.
- [x] Confirm PVC provisioning uses the intended K3s StorageClass.

**Pass:** every target namespace has the required Secret names and can
provision its own PVC. Do not print Secret values into logs.

## Phase 3 — Deploy and verify DEV

Status on 2026-10-21: **complete**. See [Phase 3 report](PHASE3_REPORT.md).
DEV's application PVC is Bound, PostgreSQL and all application Deployments are
Ready, prestart completed, and private browser login plus persisted item
creation/read/update passed. The initially generated administrator passwords
exceeded the application limit; they were corrected to 32 characters in ignored
recovery and the three backend Secrets. No database passwords or signing keys
changed. A bootstrap length guard now prevents that error.

The retained DEV marker is recorded in `/home/root-admin/liora-render/dev/acceptance.json`
for Phase 4 isolation checks. Public routing and trusted TLS remain unverified.
At Phase 3 completion STAGE/PROD application workloads were not deployed.
STAGE was subsequently deployed and verified in Phase 4 below.

- [x] Deploy the DEV overlay to `app-dev` on the dev/stage cluster. Bring up
      PostgreSQL before relying on the prestart migration Job.
- [x] Check PVC Bound, PostgreSQL Ready, prestart Complete, and backend,
      frontend, and Adminer Ready.
- [x] Through private access, check backend health, UI login, and a basic
      read/write operation against the DEV database. Record applied digests.

**Pass:** DEV works end to end without public DNS or TLS. With direct
`kubectl apply`, Argo CD sync-wave and hook annotations do not order the
prestart Job; verify database readiness and Job completion explicitly.

## Phase 4 — Deploy and verify STAGE

Status on 2026-10-21: **complete**. See [Phase 4 report](PHASE4_REPORT.md).
STAGE's separate 1Gi local-path PVC is Bound, all four Deployments have one
Ready replica, and prestart completed. Private browser login, item creation,
editing and persistence passed. Both environments return their own marker and
404 for the other marker; direct SQL confirms one own row and zero foreign
rows. Cross-environment tokens are rejected with HTTP 403. DEV stayed healthy
with unchanged workloads and zero restarts. All six nodes are Ready.

Both synthetic markers were retained through Phase 5, then removed after all
three environments passed mutual isolation. PROD deployment is recorded below;
public routing and trusted TLS remain pending.

- [x] Deploy the STAGE overlay to `app-stage` on the dev/stage cluster, with
      its own Secrets and PVC. Verify PostgreSQL before the prestart Job.
- [x] Check workloads, backend health, UI login, and a database read/write
      operation through private access.
- [x] Confirm DEV stays healthy and STAGE data remains isolated.

**Pass:** DEV and STAGE work independently on VMs 201–203.

## Phase 5 — Deploy and verify PROD

Status on 2026-10-21: **complete**. See [Phase 5 report](PHASE5_REPORT.md).
PROD's own 1Gi local-path PVC is Bound and prestart completed. PostgreSQL and
Adminer are Ready; two backend and two frontend replicas are Ready on k3s-2
nodes. Initial four-worker backend Pods repeatedly lost child workers, with no
recorded cgroup OOM kills. The explicit single-worker command used by DEV/STAGE
resolved readiness while retaining two PROD replicas and the approved digests.
The underlying multiworker failure remains unconfirmed; this is not a load test.

Private browser login and item creation/editing/persistence passed. All six
directed marker checks and six foreign-token checks passed. SQL found only each environment's own
marker. The three synthetic items were then removed, with API/SQL absence and
health rechecked. DEV/STAGE workload snapshots stayed unchanged, with zero
restarts; all six nodes are Ready. Public routing and trusted TLS remain pending.
Phase 6 has not started.

- [x] Deploy the PROD overlay with real, selected image digests to `app-prod`
      on the prod cluster, with its own Secrets and PVC.
- [x] Check prestart, both application replicas, backend health, UI login,
      and a database read/write operation through private access.
- [x] Confirm PROD runs on VMs 211–213 and both nonprod environments remain
      healthy. Record the deployed digests.

**Pass:** all three environments run the current stack on their assigned
clusters. Public routing and real domains come later.

## Phase 6 — Install separate Argo CD instances

Status on 2026-10-21: **complete**. See [Phase 6 report](PHASE6_REPORT.md).
Both independent Argo CD v3.5.6 installations and private UI logins passed.
Manual, hook-enabled application adoption and both root reconciliations passed.
The operator authorized integration and publication; the history-preserving
branch was fast-forwarded into original `main` and published. The latest
operator runbook edits were preserved.

Both roots and all three children are Synced/Healthy with automation and
self-healing enabled. Nonprod child pruning was enabled after reviewing the
12-resource inventories with no unexpected prune candidates. PROD and both
roots keep pruning disabled; PVC retention annotations remain. Each environment
passed an automated ConfigMap drift correction. Original application Pod, PVC,
Secret and Deployment identities, data bindings and schema revision remain
unchanged; private application login/health checks passed. Phase 7 has not started.

- [x] Install one Argo CD in dev/stage and another in prod; check both admin
      UIs through private access.
- [x] Adapt application-repository `argocd/app-dev.yaml`,
      `app-stage.yaml`, and `project.yaml` into
      `kubernetes/gitops/argocd/nonprod/`. Create the PROD Application and
      project in `kubernetes/gitops/argocd/prod/`. Source this repository.
- [x] Target each Application at its **local** cluster and correct namespace.
      Inspect diffs before Argo CD takes ownership of the manual deployment;
      enable automation only after correct reconciliation. Review the effects
      of pruning separately.
- [x] Verify correct digests, healthy workloads, and no unexpected deletion
      in each Argo CD instance.

**Pass:** each Argo CD manages only its own cluster. Do not copy
`argocd/applicationset.yaml` unchanged: it targets all three environments
in one cluster.

## Phase 7 — Publish the application

- [ ] Configure real DEV, STAGE, and PROD hostnames, DNS, ingress, and TLS.
      Replace `*.example.com`; align backend CORS and frontend settings.
- [ ] Establish distinct ingress addresses and edge routing. Current kube-vip
      covers the **API VIPs only** and K3s ServiceLB is enabled. Decide ingress
      addressing before adding HAProxy and Proxmox TCP/443 DNAT.
- [ ] Verify each hostname reaches only its intended environment and that
      valid TLS, UI login, and the API work.

**Pass:** the application works at its real URLs. Keep Argo CD, Adminer, and
other admin interfaces behind Tailscale or equivalent private access.

## Phase 8 — Add monitoring and operational access

- [ ] Adapt the application repository's `monitoring/` inputs for K3s
      storage and actual service labels; install dev/stage monitoring.
- [ ] Install separate prod monitoring with its own retention and alerts.
- [ ] Check Grafana, Prometheus, Argo CD, and application admin access through
      the private path. Verify dashboards identify the right cluster and
      environment, then send a test alert.

**Pass:** both clusters report useful metrics and alerts and operators can
reach their administrative interfaces.

## Phase 9 — Move promotion and CI ownership

- [ ] Keep build/test and image publication in the application repository.
      Change promotion tooling to propose reviewed digest updates to this
      infrastructure repository rather than its former `deploy/overlays/`.
- [ ] Add checks to render all overlays and reject placeholder PROD images.
      Review one DEV → STAGE → PROD promotion.
- [ ] Verify Argo CD deploys the reviewed digests and can roll back. Retire
      old GitOps source paths only after this succeeds.

**Pass:** promotion, release history, and rollback work across the two
repository boundaries.

## Phase 10 — Replace temporary components incrementally

- [ ] Test database backup and restore before replacing the current
      PostgreSQL Deployment. Introduce CloudNativePG one environment at a
      time, beginning with DEV.
- [ ] Add per-cluster Secret encryption and recovery keys, certificate
      automation, and dedicated ingress addresses in separate changes.
      Check each on DEV, then STAGE, then PROD.
- [ ] Remove Adminer and other lab-only resources only after a replacement
      operational path works. Recheck both clusters' recovery procedures.

**Pass:** target services replace the initial stack without losing data,
access, or a tested recovery path.
