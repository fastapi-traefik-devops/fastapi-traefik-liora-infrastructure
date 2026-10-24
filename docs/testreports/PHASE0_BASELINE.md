# Phase 0 baseline — 2026-10-21

## Scope and provenance

Phase 0 only. Phase 1 requires explicit confirmation after this report.
No namespace, Secret, PVC, workload, routing, or other cluster resource was
created or changed. The application checkout was inspected read-only and was
clean. No history import, merge into the original branch, or push was made.

- Infrastructure baseline: `1c903732e5b320fc4acd2f8ff67fcbdc523ebca7`.
- Isolated branch: `migration/liora-phase0`.
- Worktree: `/tmp/liora-migration-phase0`.
- Application origin: `git@github.com:fastapi-traefik-devops/fastapi-traefik-liora-application.git`.
- Application source HEAD: `1a5b24f096dd1a6234fa101f8648e40db88b52c7`.
- The plan's earlier review commit `3a610ebb14f265fcdeb5a1d4d59da9fa543648c5`
  remains STAGE's image source, not the manifest checkout HEAD.
- Supplied `IMPLEMENTATION_PLAN.md` and `StartPrompt.md` were carried into
  the isolated worktree because both were untracked in the original checkout.

Read README, architecture, the entire implementation plan, installation and
recovery navigators, VM provisioning and K3s installation runbooks, and every
file in the current deployment base and three overlays. The committed
infrastructure ends at cluster bootstrap; it contains no active application
manifests. Historical `k8s/` is not a deployment source.

## Cluster and capacity observations

Read-only checks used explicit kubeconfigs throughout:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get nodes -o wide
kubectl --kubeconfig="$HOME/.kube/config-prod" get nodes -o wide
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get storageclass,pv,pvc -A
kubectl --kubeconfig="$HOME/.kube/config-prod" get storageclass,pv,pvc -A
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" describe nodes
kubectl --kubeconfig="$HOME/.kube/config-prod" describe nodes
```

Contexts are `dev-stage` at `https://192.168.77.11:6443` and `prod` at
`https://192.168.77.12:6443`. Nodes `k3s-1-01` through `k3s-1-03` and
`k3s-2-01` through `k3s-2-03` are all Ready on `v1.36.5+k3s1` at their
expected addresses. Each reports 2 allocatable CPUs and approximately
7.6–7.8 GiB allocatable memory; no memory, disk, or PID pressure is reported.
Existing reservations total 200m CPU and 140Mi memory per cluster.

Both clusters have the default `local-path` StorageClass, provisioner
`rancher.io/local-path`, `WaitForFirstConsumer`, reclaim policy `Delete`,
and no volume expansion. Both provisioner Pods are Running. Its configured
path is `/var/lib/rancher/k3s/storage`. Node filesystem summaries report
approximately 186–187 GiB available per node. These are filesystem observations,
not storage reservations or proof of successful PVC provisioning. No PVs or
PVCs exist. A provisioning test is deferred because this increment prohibits
cluster mutations. Local-path volumes are node-local, not replicated database
storage; do not infer data redundancy from the three-server control plane.

Each environment requests one 1Gi ReadWriteOnce PostgreSQL PVC, with no explicit
StorageClass. DEV/STAGE each request 500m CPU and 576Mi memory at steady state;
each prestart Job adds 100m and 128Mi while running. Together, DEV/STAGE plus
both Jobs request 1200m and 1408Mi. PROD requests 700m and 832Mi, plus 100m and
128Mi for prestart. Reported capacity exceeds these requests and existing
reservations. This is a scheduling baseline, not a runtime load test, peak
rollout guarantee, or Proxmox physical-memory validation.

Only the standard namespaces exist; `app-dev`, `app-stage`, and `app-prod`
and their three required Secrets are absent. Traefik and ServiceLB are
Running. Public ingress and application acceptance were not tested.

## Source render results

Local renders used `kubectl --kubeconfig="$HOME/.kube/config-dev-stage"
kustomize` for DEV/STAGE and the explicit PROD kubeconfig for PROD, targeting
the read-only application's `deploy/overlays/<environment>` directory.
All three renders exited successfully, each yielding 13 namespaced resources:
two ConfigMaps, four Deployments, four Services, one PVC, one Job, and one
Ingress. No Namespace or Secret objects are generated.

| Overlay | Namespace | Backend / frontend replicas | Ingress | TLS dependency |
| --- | --- | --- | --- | --- |
| DEV | app-dev | 1 / 1 | dev.example.com; /api, /, /docs | None |
| STAGE | app-stage | 1 / 1 | stage.example.com; /api, / | app-tls |
| PROD | app-prod | 2 / 2 | prod.example.com; /api, / | app-tls |

All retain PostgreSQL `postgres:16.6`, Adminer `adminer:4.8.1`, and prestart.
Backend and prestart require `backend-secrets`; PostgreSQL requires
`db-secrets`; backend, frontend, and prestart require `ghcr-pull-secret`.
STAGE/PROD also reference `app-tls`; this is an additional dependency for
trusted HTTPS, distinct from the three application Secrets. Real hostnames,
public routing and TLS automation remain later work. Preserve the source
configuration, including DEV's `ENVIRONMENT: staging`, DEV's HTTP settings,
and the single-worker backend overrides in DEV/STAGE.

Application image repositories are
`ghcr.io/fastapi-traefik-devops/fastapi-backend` and
`ghcr.io/fastapi-traefik-devops/fastapi-frontend`.

| Overlay | Component | Digest |
| --- | --- | --- |
| DEV | backend and prestart | `sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b` |
| DEV | frontend | `sha256:a8d07b6be8ae8c76cc8133c885ba8ec3c095ded005db251aaf6a190e88426f82` |
| STAGE | backend and prestart | `sha256:a46062cca28e9b0618777adda1fd500832a086552766c573b290478b3afb82ee` |
| STAGE | frontend | `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |
| PROD | backend, frontend and prestart | Unselected; placeholder tags only |

DEV tag is `sha-3303e93b753e8282dc7b461c583fb8ace43574a1`; STAGE tag is
`sha-3a610ebb14f265fcdeb5a1d4d59da9fa543648c5`. Both renders include tag and
digest; the digest pins the image. PROD renders with
`sha-0000000000000000000000000000000000000000` and no digest. No release was
invented. Registry authentication and manifest availability were verified in the follow-up
below. Full image-layer pulls were not tested.

## Credential readiness

Only key presence and obvious placeholder status were inspected; no values
are reproduced or copied. Infrastructure `recovery/.env` has populated
`GHCR_REGISTRY`, `GHCR_USERNAME`, and `GHCR_TOKEN` fields. Authenticated GHCR token issuance, tag listing, and manifest reads succeeded
for both application repositories. Cluster-side image pulls remain untested.
`recovery/recovery.yaml` identifies a nonprod legacy encryption controller-key
location, not a verified backup of the required application Secrets.
Do not import old ciphertext or controller keys in this phase.

The application checkout's `.env` has obvious placeholders for `SECRET_KEY`,
`FIRST_SUPERUSER_PASSWORD`, and `POSTGRES_PASSWORD`; `SMTP_PASSWORD` is empty.
It is not a usable recovery credential source. Required backend fields include
`SECRET_KEY`, `FIRST_SUPERUSER_PASSWORD`, and `POSTGRES_PASSWORD`; database
`POSTGRES_PASSWORD` must agree with the backend. SMTP credentials are optional
when SMTP is disabled. The operator must identify the external recovery archive
or arrange separate credentials for DEV, STAGE and PROD. Do not reuse this
placeholder environment file or commit live values. No suitable per-environment
application credential archive has been verified.

## Minimum Phase 1 change and history strategy

Import the 14 files under `deploy/base/` and the five files under
`deploy/overlays/{dev,stage,prod}/` into `kubernetes/apps/liora/`, preserving
relative paths. The two `promotion.json` files retain provenance but are not
render inputs. All current overlays render without compatibility changes;
no K3s rendering adjustment is currently justified. The required image change
is the operator's approved existing PROD backend/frontend digests.

Five source commits touch the selected paths. `git-filter-repo` and `gitleaks`
are not installed in the current command environment. In Phase 1, prepare a
disposable clone pinned to the recorded HEAD, obtain suitable filtering and
credential-scanning tooling, and scan every selected historical blob before
importing any history. This scan has not been performed. Stop and report paths
and remediation options if credentials are found; never print values.

Filter to only those selected deployment paths, preserving author metadata
and messages as practical; do not pull in the whole repository or historical
`k8s/`. Merge the filtered history with unrelated histories on an isolated
migration branch, then move files to the final paths. Record source and
rewritten commit mappings, compare imported content with the source, and verify
historical file changes using `git log --follow` and representative `git show`
checks. Review-only commits stay on that branch; no merge into the original
branch or push is authorized.

Phase 1 must also add `runbooks/13-deploy-application-manifests.md` and step 10
in both installation/recovery navigators. Document explicit kubeconfigs,
namespace/Secret prerequisites, staged PostgreSQL → prestart → application
ordering, separate environment acceptance, and the independent data-restore
procedure. Argo annotations do not sequence a direct kubectl apply. These
runbook edits are deferred until the manifests exist, as instructed.

## Phase status and next decisions

- Complete: both distinct cluster contexts work and all six nodes are Ready.
- Partial: source commit and DEV/STAGE image references recorded; PROD image
  selection needs the operator's decision.
- Partial: default StorageClasses, provisioner health and reported capacity
  checked; actual PVC provisioning remains unverified without a permitted
  later cluster test.
- Partial: GHCR candidate located; usable per-environment backend/database
  credentials remain unverified; management-host registry read access is verified.

Phase 0 has not passed. Next: obtain approved existing PROD backend/frontend
digests, identify the real external credential recovery source and environment
mapping, and agree how to defer the storage provisioning check to the permitted
cluster deployment phase. Then confirm whether to begin Phase 1. Do not start
Phase 1 or execute Phase 2 and later without that confirmation.

## Access and registry follow-up — 2026-10-21

A temporary file was successfully written, read, and removed in the original
infrastructure checkout outside `/tmp`. Both specified recovery files are
readable, mode `0600`, ignored by Git, and untracked. No credential values
were printed, committed, rewritten, or sent to unrelated services.

Authenticated GHCR requests using the recovery credentials returned HTTP 200
for token issuance, tag listing, and DEV/STAGE manifest reads by both tag and
digest. All four registry digests exactly match the source overlays above.
Both repositories also expose `v0.1.0`, `latest`, and additional SHA tags.
These tag listings do not constitute approval of any first PROD release.
Using the current STAGE pair for the first educational PROD deployment is a
concrete available option requiring the operator's selection. Image layers
were not downloaded and no live cluster pull was attempted.

`recovery.yaml` contains two populated nonprod legacy encryption controller
certificate/private-key pairs; it does not contain backend/database Secret
values for the three target environments. Historical application DEV
legacy encrypted credential files exist and have relevant key names, but decryptability and
credential suitability have not been verified. They were not imported,
decrypted, or applied. This inventory does not establish usable credentials
for STAGE or PROD.

Next clarification: select an existing PROD image pair and choose whether to
generate fresh, separate lab application credentials in ignored recovery files
or recover existing values. Phase 1 still awaits explicit confirmation.

## Fresh credentials and kind reference — 2026-10-21

The operator approved generating fresh application credentials for each of the
three educational K3s environments. They are stored only in the original
checkout's ignored `recovery/recovery.yaml`, under `application_credentials`.
Each environment has its namespace, initial administrator email matching the
ConfigMap (`admin@example.com`), `backend-secrets` fields, and `db-secrets`
fields. The nine generated values (three per environment) are independent,
cryptographically random URL-safe strings. Each environment's backend/database
passwords agree. SMTP password remains empty because SMTP is disabled.

Validation confirmed all required fields are present, values are distinct
across environments and purposes, the file is untracked and ignored, mode is
`0600`, and existing controller recovery material is unchanged. No generated
values appear in Git or this report. No Kubernetes Secrets have been created.
The isolated worktree has no copied credential material; later procedures
must refer to the original ignored recovery files explicitly.

With the operator's permission, read-only discovery used the existing kind
cluster's explicit kubeconfig `/home/root-admin/.kube/config`. DEV matches
the recorded source overlay images. Its STAGE Deployments instead reference:

- Backend tag `sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`, digest
  `sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d`.
- Frontend tag `sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`, digest
  `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91`.

STAGE backend, frontend, PostgreSQL and Adminer Pods report Running and Ready.
This is workload readiness, not an end-to-end acceptance test. The local
application checkout remains clean at the recorded source HEAD. Do not
silently substitute kind's live STAGE backend digest for the source overlay.

Credential discovery is now complete for the planned initial deployment.
There is enough information for Phase 1's independent history-import and
runbook work. PROD still needs an explicitly approved existing image pair,
and PVC provisioning remains deferred to a later authorized cluster phase.
Phase 1 has not begun: this turn requested readiness checking and credential
generation. Ask whether to use the repository's STAGE pair or kind's live
STAGE pair for PROD and obtain confirmation before starting Phase 1.
