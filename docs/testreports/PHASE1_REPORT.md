# Phase 1 report — current application deployment import

Status on 2026-10-21: **complete for local import and rendering**. The operator
approved the current STAGE images for PROD, now pinned by digest. Phase 2 and
later have not started.

## Source and isolated work

- Source repository: `https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application`.
- Source HEAD: upstream `b98a22e48527c256193ed65c10307eb574b27ab6`.
- The clean, read-only local checkout remains at
  `1a5b24f096dd1a6234fa101f8648e40db88b52c7`. The newer upstream STAGE
  promotion was discovered and imported from a disposable clone without
  changing that checkout; current STAGE now matches kind.
- Migration branch: `migration/liora-phase0`.
- Current worktree: `/home/root-admin/liora-infrastructure-migration`, moved from
  its initial temporary location at the operator's request.
- Original infrastructure `main` remains at
  `1c903732e5b320fc4acd2f8ff67fcbdc523ebca7`. No merge into it or push was made.

The operator explicitly authorized proceeding after the Phase 0 report, despite
PROD release selection and a live provisioning test still being outstanding.
Only local import, configuration, runbook and validation work was performed.

## Files introduced and changed

All 14 files below were imported from `deploy/base/` to
`kubernetes/apps/liora/base/` with history. Only the initial administrator email
in `configmap-backend.yaml` was subsequently changed:

```text
configmap-backend.yaml
configmap-db.yaml
deployment-adminer.yaml
deployment-backend.yaml
deployment-db.yaml
deployment-frontend.yaml
ingress-app.yaml
job-prestart.yaml
kustomization.yaml
pvc-db.yaml
service-adminer.yaml
service-backend.yaml
service-db.yaml
service-frontend.yaml
```

The five imported overlay files are:

```text
kubernetes/apps/liora/overlays/dev/kustomization.yaml
kubernetes/apps/liora/overlays/dev/promotion.json
kubernetes/apps/liora/overlays/stage/kustomization.yaml
kubernetes/apps/liora/overlays/stage/promotion.json
kubernetes/apps/liora/overlays/prod/kustomization.yaml
```

Each Kustomization received the requested domain substitutions. Both
promotion records match current upstream and are not deployment inputs. DEV/STAGE
image pins and all workload configuration match the current source. After the
operator approved the current STAGE pair, PROD placeholders were replaced with
those exact tags and digests; the remainder of its configuration is preserved.

| Other file | Purpose |
| --- | --- |
| `docs/testreports/MIGRATION.md` | Source provenance, scan procedure, metadata preservation and history inspection examples |
| `kubernetes/apps/liora/SOURCE_HISTORY.tsv` | Eight original-to-filtered commit mappings |
| `runbooks/13-deploy-application-manifests.md` | Actual staged deployment procedure, Secret prerequisites, PostgreSQL/prestart gates, environment acceptance and recovery boundaries |
| `00-Installation_from-0.md` | Add step 10 linking the new application runbook after K3s installation |
| `01-Disaster_recovery.md` | Add the corresponding recovery step 10; database restore remains separate |
| `README.md` | Add application path and deployment runbook with current verification status |
| `docs/ARCHITECTURE.md` | Record manifest ownership and distinguish local import from live deployment |
| `docs/testreports/IMPLEMENTATION_PLAN.md` | Mark verified Phase 1 items, record requested configuration, keep PROD and live checks open |
| `docs/testreports/APPLICATION_REPOSITORY_CLEANUP.md` | Update migration status; no application deletion is authorized |
| `docs/testreports/PHASE1_REPORT.md` | This review record |

Local-only change outside this branch: the ignored original checkout's
`recovery/recovery.yaml` now uses `admin007@liora.aprt.info` for all three
`application_credentials.<environment>.first_superuser` fields. The previously
generated independent credential values and controller keys were preserved.
No credential file was copied into the migration worktree or added to Git.

## History preservation and credential review

The initial disposable clone was followed by an upstream review clone at
`/home/root-admin/liora-upstream-review`, filtered to exactly the current base
and three overlays with git-filter-repo 2.47.0. The current history retains
six change commits and two merge commits. All original author/committer identities, timestamps, messages, and selected file trees were
compared successfully. All 25 historical blob IDs are unchanged.

Before importing history, Gitleaks 8.30.1 scanned all 25 unique historical blobs
through six change snapshots (110 file instances), without source suppressions.
No credentials or Secret/SealedSecret resources were found. The filtered history
and final application directory also passed scans. Merge-tree blob coverage was
checked against the pre-import snapshot inventory. This establishes the stated
scan coverage, not a guarantee about every possible credential pattern.

The unrelated-history merge is `412e465`; the Git move and provenance commit is
`85e5624`; the requested domain/email configuration commit is `dafb839`;
the upstream STAGE promotion was merged with preserved history in `07a72d2`.
`git log --follow` on STAGE's Kustomization reaches its original promotion and
single-worker changes, and on the PostgreSQL Deployment reaches its original
creation. A representative historical file was compared via `git show`.
No unrelated application, `k8s/`, Argo CD, monitoring or Jenkins files were imported.

## Local render results

All three renders used their intended explicit kubeconfigs and succeeded.
Each yields 13 resources: two ConfigMaps, four Deployments, four Services,
one PostgreSQL PVC, one prestart Job, and one Ingress. They create no Namespace
or Secret objects. Parsed output was compared with the application source:
the only differences are the requested domains, initial administrator email,
and the approved PROD image pins.
No K3s compatibility edit was required to render this deployment.

| Environment | Namespace | Backend / frontend replicas | Ingress host | Origin / TLS |
| --- | --- | --- | --- | --- |
| DEV | app-dev | 1 / 1 | dev.liora.aprt.info | HTTP; no TLS block |
| STAGE | app-stage | 1 / 1 | stage.liora.aprt.info | HTTPS; app-tls |
| PROD | app-prod | 2 / 2 | liora.aprt.info | HTTPS; app-tls |

The initial account is `admin007@liora.aprt.info` in each separate database.
DEV retains `ENVIRONMENT: staging` and its `/docs` ingress route. STAGE/PROD
retain source TLS requirements. Setting real hostnames does not provision DNS,
certificates, edge routing or public ingress. The source base's generic host is
overridden in all deployed overlays.

Each environment retains PostgreSQL `postgres:16.6`, Adminer `adminer:4.8.1`,
one 1Gi ReadWriteOnce PVC with the default StorageClass, and prestart using the
same image as its backend. `ghcr-pull-secret`, `backend-secrets`, and `db-secrets`
remain required; STAGE/PROD also reference `app-tls` for trusted HTTPS.

DEV retains its Phase 0 image pins; STAGE now uses the current upstream
promotion, matching kind. These references were verified against GHCR:

| Environment | Component | Digest |
| --- | --- | --- |
| DEV | backend and prestart | `sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b` |
| DEV | frontend | `sha256:a8d07b6be8ae8c76cc8133c885ba8ec3c095ded005db251aaf6a190e88426f82` |
| STAGE | backend and prestart | `sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` |
| STAGE | frontend | `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |
| PROD | backend and prestart | `sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` |
| PROD | frontend | `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |

DEV tag is `sha-3303e93b753e8282dc7b461c583fb8ace43574a1`; STAGE tag is
`sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`. PROD now uses that approved
STAGE tag and digest pair. All three overlays render without placeholder or
unconfigured application images. Live deployment remains unverified.

The runbook's shell blocks and embedded Python snippets were parsed locally.
Its offline splitting step was executed for DEV, STAGE and PROD: groups contain
3 configuration/storage, 2 database, 1 prestart and 7 application resources.
Before approval, the same step rejected the original PROD placeholders before
any cluster writes; the approved PROD render now passes. Local
recovery schema, matching administrator identities and database passwords, Git
ignore status, relative documentation links, and whitespace checks passed.
No live bootstrap, apply, rollout, port-forward, UI login or data checks ran.

## Phase checklist and remaining decisions

- Complete: current base imported in full with selected Git history.
- Complete: all three overlays and both promotion records imported with history.
- Complete: all three overlays rendered; namespaces, images, replicas, Secret
  dependencies, PVC and Ingress configuration inspected.
- Complete: deployment runbook and both navigator step 10 links added.
- Complete: requested domains and initial administrator email aligned with
  the ignored recovery file.
- Complete: the operator explicitly approved current upstream/kind STAGE
  images (`sha-c375967...`) for PROD; backend, frontend and prestart render
  with the approved digests.
- Deferred to later authorized cluster phases: namespace/Secret creation,
  actual PVC provisioning, database readiness, prestart completion, image pulls,
  application acceptance, and data isolation checks.
- Deferred: DNS, TLS certificate setup, public routing, GitOps, monitoring,
  database migration and CI ownership changes.

Next small action: review this completed local increment and confirm Phase 2
namespace/Secret preparation. Phase 2 and all later cluster changes remain
unexecuted. The storage provisioning and application acceptance checks belong
to those later authorized phases, not to local Phase 1 completion.
