# Phase 2 report — namespace and credential preparation

Status on 2026-10-21: **complete**. Phase 3 has not started.

## Scope and source

The operator explicitly authorized the next phase after reviewing Phase 1.
Changes were limited to three namespaces, their nine required Secrets, and
temporary storage verification resources. No database or application workload,
prestart Job, ingress, Argo CD, monitoring or public routing was deployed.

The application source remains upstream
`b98a22e48527c256193ed65c10307eb574b27ab6`, imported with history in Phase 1.
No application manifests or image pins changed in this phase. DEV, STAGE and
PROD overlays retain their successful 13-resource renders. Live application
rollout, image pulls for those workloads, UI login and data acceptance are not
verified by namespace preparation.

Work remains on `migration/liora-phase0` in
`/home/root-admin/liora-infrastructure-migration`. The original infrastructure
branch and application checkout were not modified, merged into, or pushed.
Live recovery values remain only in ignored original-checkout recovery files
and the explicitly authorized Kubernetes Secrets; no values appear in Git.

## Namespace and Secret results

Explicit kubeconfigs were used for every cluster-dependent operation. Both API
VIPs and the exact node identities were checked before writes. All six nodes
were Ready before and after the checks.

| Cluster | API server | Active namespaces |
| --- | --- | --- |
| dev-stage | https://192.168.77.11:6443 | app-dev, app-stage |
| prod | https://192.168.77.12:6443 | app-prod |

Each namespace has exactly these required Secrets:

| Name | Type | Required fields verified |
| --- | --- | --- |
| backend-secrets | Opaque | SECRET_KEY, FIRST_SUPERUSER_PASSWORD, POSTGRES_PASSWORD, SMTP_PASSWORD |
| db-secrets | Opaque | POSTGRES_PASSWORD |
| ghcr-pull-secret | kubernetes.io/dockerconfigjson | .dockerconfigjson with ghcr.io credentials |

The existing standalone `bootstrap-application-secrets.py` was executed once
per fresh namespace with that environment's explicit kubeconfig and recovery
location. All live values were decoded and compared in memory with the local
recovery records; none was logged. Backend/database passwords agree within
each environment. The nine generated application credential values remain
independent across environments and purposes. GHCR username, token and encoded
auth fields agree with ignored `recovery/.env`. The initial administrator
identity remains `admin007@liora.aprt.info` in configuration and recovery.
SMTP password is empty because SMTP is disabled.

The local recovery files remain ignored, untracked and mode `0600`. The
namespace-local `app-tls` Secrets were not created: trusted HTTPS setup remains
a separate prerequisite before HTTPS acceptance. No Secrets were copied from
the existing kind reference cluster, and kind was not changed.

## Storage verification and cleanup

Both clusters have one default StorageClass, `local-path`, provisioned by
`rancher.io/local-path`, with `WaitForFirstConsumer` and reclaim policy `Delete`.
The reusable probe requests 1Gi RWO with no explicit StorageClass, matching the
application's PVC selection behavior. Its consumer Pod runs only shell commands
using `postgres:16.6`; it does not launch PostgreSQL or consume application
Secrets. Each Pod wrote, flushed and read its namespace marker from its own PVC.

| Namespace | Probe node | Dynamically provisioned PV, subsequently removed | Attempts |
| --- | --- | --- | --- |
| app-dev | k3s-1-02 | `pvc-d33a8c30-ae2c-4f35-92f6-53af9492675d` | 1 |
| app-stage | k3s-1-03 | `pvc-92145643-4fdb-4efd-8681-f818bc1253df` | 2 |
| app-prod | k3s-2-02 | `pvc-c4c5fd6f-c25c-4f29-a0b8-21f51be4be32` | 1 |

All three claims reached Bound, used `local-path`, had distinct PVs and correct
namespace/UID claim references, and had PV node affinity matching the actual
consumer node. All three final Pods reached Succeeded and logged the expected
namespace marker. This proves basic provisioning and mounted file I/O, not
storage replication, database readiness, backup recovery or node failover.

The first STAGE Pod terminated with runtime reason `Unknown`, exit code 255,
at 14:49:26 UTC. Node events reported kubelet startup at that time; the cause of
the runtime interruption was not established. With the node Ready, only the
owned failed test Pod was recreated, retaining its bound test PVC. The second
Pod succeeded on the same node, `k3s-1-03`, without any node/service restart or
infrastructure change by this phase. DEV and PROD passed on their first attempt.
This transient observation remains part of the record; it is not a verified
root-cause diagnosis or a node-failure recovery test.

Before cleanup, live resource UIDs were compared with the resources created
by this check. Only the owned `liora-storage-check` Pods and PVCs were deleted.
All three dynamic PVs were confirmed deleted after reclamation. Final checks
found no Pods, PVCs, Deployments, Jobs, application ConfigMaps, Services or Ingress
objects in the application namespaces. The standard kube-root-ca.crt ConfigMap
and default ServiceAccount are cluster-managed. Each namespace retains its
three required Secrets; the application `postgres-vol` claims do not exist yet.

## Repository files added or changed

| File | Reason |
| --- | --- |
| runbooks/_resources/application-storage-check.yaml | Reusable temporary 1Gi PVC and shell-only consumer Pod |
| runbooks/13-deploy-application-manifests.md | Link the probe manifest and document creation, success checks and precise cleanup; record Phase 2 status |
| README.md | Reflect completed preparation without claiming application deployment |
| docs/testreports/IMPLEMENTATION_PLAN.md | Mark Phase 2 and the deferred baseline storage item complete; keep Phase 3 and later unchecked |
| docs/testreports/phases/phase-02/history/execution-2026-10-21.md | This evidence, observed interruption, cleanup record and scope boundary |

The inline Python scripts and standalone script copies remain unchanged and
identical. The new storage procedure consists of individual kubectl commands
and a linked manifest, so it needs no additional shell-script wrapper.

## Checklist and next actions

- Complete: correct namespaces exist only on their assigned clusters.
- Complete: each namespace has the three required Secrets with correct types,
  keys and recovery values; backend/database credentials agree.
- Complete: all three namespaces provision a default local-path PVC and pass
  mounted write/read checks; temporary resources and PVs are cleaned up.
- No Phase 2 blockers remain. The STAGE interruption is documented above.
- Deferred: actual application PVCs, database startup, prestart migrations,
  backend/frontend/Adminer readiness, application acceptance and trusted TLS.

Next small action, after explicit Phase 3 confirmation: deploy DEV only, bring
PostgreSQL Ready, complete prestart, then start and verify DEV through private
access. Do not deploy STAGE or PROD during Phase 3. Stop after the DEV report
before beginning the next phase.
