# Phase 6 report — independent Argo CD instances

Status on 2026-10-21: **complete**. Phase 7 has not started.

## Implementation and provenance

Worktree `/home/root-admin/liora-argocd-phase6`, branch
`migration/liora-phase6`, based on original main `206b394`. The operator's newer
runbook readability commit `0588b5a` was merged without changing its contents.
After explicit operator approval, original main was fast-forwarded to
`c75d261e2749f6d0dc1b71bf6f41f217424b4968` and pushed to origin. No imported
history was rewritten. Work then continued in the original checkout on main.
Commit `cc2c210` publishes the reviewed automation and pruning policies.

Application source: `b98a22e48527c256193ed65c10307eb574b27ab6`. Only
`argocd/app-dev.yaml`, `argocd/app-stage.yaml` and `argocd/project.yaml` were
selectively imported with history, then moved and adapted. Three historical
change commits and three unique blobs passed pre-import scanning; the filtered
history retains five commits including merges. Author/committer identity,
timestamps, messages and selected blob IDs were compared with the read-only
source. See `kubernetes/gitops/argocd/SOURCE_HISTORY.tsv`. The unrelated-history
import is `f2efaae`; adaptation and install configuration are `8256649`.

The official Argo CD v3.5.6 manifest is pinned to upstream commit
`c2b1e3017e2cec86b122172e861dcd026453ae44`, SHA-256
`846c644bc81ce5557dd9048757a9c7353378f25c5eb811c77d32a9e907823599`.
The install renders 59 objects: three CRDs, seven ServiceAccounts, six Roles,
three ClusterRoles, six RoleBindings, three ClusterRoleBindings, seven
ConfigMaps, two empty bootstrap Secrets, eight Services, six Deployments, one
StatefulSet and seven NetworkPolicies. Local patches set modest resource
requests and memory limits, without CPU limits, for the slow shared host.
The version and source are documented in `install/UPSTREAM.md`.

## Live installation and private access

Every cluster operation used an explicit kubeconfig. Nonprod API
`192.168.77.11:6443` has its own installation in `argocd`; PROD API
`192.168.77.12:6443` has an independent installation in the same namespace name.
Both have seven Ready component Pods and ClusterIP Services, with no public
Ingress, NodePort or LoadBalancer added. Tracking uses annotations and distinct
installation IDs `liora-nonprod` and `liora-prod`. No external cluster was
registered, and the old all-environment ApplicationSet was not imported.

Startup included temporary missing Redis Secret errors until Redis initialization
completed. Both APIs briefly became unavailable during installation and recovered
without operator node restarts. Nonprod application-controller recorded one
restart and server one restart (Unknown/255); PROD Dex recorded three restarts
(Error/20), then became Ready. The underlying API/runtime interruption cause is
unconfirmed. Do not describe these observations as a tested failover or OOM.

Actual private UI login and authenticated user-info API passed for both instances,
using the standalone `scripts/kubernetes/verify-argocd-ui.py`. Passwords were read
from each cluster's initial-admin Secret only in memory; no password, session
token, browser state or trace was saved. The helper uses loopback Service
forwards, self-signed bootstrap HTTPS and a three-minute browser timeout. This
does not establish public trusted TLS. Initial credentials remain in the cluster;
the version 1 recovery YAML was not extended or overwritten.

## Application adoption and gates

The nonprod project allows only app-dev/app-stage on
`https://kubernetes.default.svc`; PROD allows only app-prod on its local API.
Child definitions source the infrastructure repository's application overlays.
All child/root definitions initially had `automated.enabled: false`,
`prune: false` and no cascading-delete finalizers during adoption. Final policies
enable automation and self-healing for all five Applications. Only nonprod
children enable pruning; PROD and both roots keep pruning disabled.

Each child was first refreshed and reviewed against published revision
`206b3946ffcab404c689a5dd68fdcf7580975371`. The 12 ordinary resources differed
only by the two Argo CD tracking annotations; no Pod template, image, replica,
PVC or credential change was proposed. The completed prestart Job was separately
identified as a hook. Manual apply-strategy syncs succeeded with pruning off;
all three children became Synced/Healthy. Exact application Pod, PVC, Secret and
Deployment UID snapshots were unchanged. Apply strategy skips hooks, so a second
manual sync used the hook strategy against the newer published `0588b5a`
revision (a runbook-only change). All three hook-enabled operations succeeded,
Synced/Healthy. Each prestart Job was replaced, completed and removed by its
hook cleanup policy. Original application Pod/PVC/Secret/Deployment identities
and database revision `1a31ce608336` were preserved. Private ingress health,
login and authenticated user checks passed for all three environments afterward.
No synthetic data was created by this phase.

## Root reconciliation, automation and pruning review

After publication, both bootstrap projects and roots were applied. Each
bootstrap project is restricted to Application/AppProject objects in its local
argocd namespace. Root inventories were inspected before syncing: nonprod
contains only fastapi, app-dev and app-stage; PROD contains only fastapi and
app-prod. Bootstrap and installation directories are excluded from root output.
Both manual root operations succeeded at published revision `c75d261`,
Synced/Healthy, with pruning off and no unexpected deletion.

Before enabling nonprod child pruning, each child inventory contained exactly
12 ordinary tracked resources in its own namespace with no prune candidates.
PVCs retained `Prune=false,Delete=false`. Existing application Secrets remain
outside GitOps inventories. No external cluster was registered and no
ApplicationSet spanning clusters was installed. Root projects are admin-level
bootstrap configuration; only reviewed operators should modify them.

Commit `cc2c210` enabled automation/self-healing for both roots and all children,
with nonprod child pruning enabled and PROD/root pruning disabled. Applying the
reviewed root bootstrap policies allowed roots to reconcile child policy changes
from Git. All five Applications report Synced/Healthy and successful operations.

Each child then received one temporary non-secret `backend-config.PROJECT_NAME`
drift. A hard refresh requested comparison; no manual sync or corrective patch
was used. All three values were restored by operations whose
`initiatedBy.automated` field was true. Operations succeeded and returned to
Synced/Healthy. No image, replica count, credential or data change was introduced.
Self-healing of missing data-bearing resources and destructive prune behavior
were deliberately not tested.

The 12 ordinary application resources preserved their original identities:
Pod, Deployment, PVC, Secret UIDs and PV bindings match the pre-adoption snapshots.
Hook Jobs were the only planned replacements/removals. Final application Pods
are Ready with zero restarts; PROD retains two backend and two frontend replicas.
Actual image IDs retain the Phase 5 approved pins. Schema revision remains
`1a31ce608336`, and private application health/login/user-info checks passed in
all three environments after reconciliation. Both Argo CD UI logins were
repeated successfully. All six nodes are Ready. Temporary private forwards
were stopped after acceptance.

## Validation and local evidence

YAML parsing, all project/root Kustomize renders, Python syntax and runbook shell
syntax passed. Historical selected blobs, filtered history and GitOps files
passed Gitleaks with no findings. Evidence is under
`/home/root-admin/liora-phase6-artifacts/`, including adoption UID snapshots and
`adoption-results.json`, `hook-adoption-results.json` and
`hook-adoption-before.json`, `root-results.json`, `self-heal-results.json` and
`final-results.json`. Evidence contains result metadata and no credentials.

`runbooks/14-install-argocd.md` documents installation, private access, publication,
diff review, hook-aware manual sync, root bootstrap, automation and pruning gates.
The UI helper is linked directly under its command. Original recovery files,
Terraform state and unrelated untracked operator documents are not modified.

## Files, checks and next phase

New tracked files live under `kubernetes/gitops/argocd/{install,nonprod,prod}`,
plus the source history map, `runbooks/14-install-argocd.md`, and
`scripts/kubernetes/{verify-argocd-ui,render-manual-argocd-bootstrap}.py`.
The manual-bootstrap filter keeps fresh installations from applying the final
automated policies before adoption review; all four child/root renders were
checked to disable automation and pruning through the filter. It validates all
input before writing output and never reads recovery credentials.

The plan, README, architecture and navigator links now describe completed Phase 6.
Original recovery files and the two untracked operator documents were left in
place and were not written by this phase. An older integration preservation
record was no longer present at the final check, so a new before/after hash
comparison against that record was unavailable. No private key, token,
credential or Terraform state was committed. Historical source scans, GitOps
scans, syntax, render, private UI and live reconciliation checks passed.

All Phase 6 checklist items are complete. Public routing/trusted TLS, monitoring,
database backups/restore, data replication and the cause of the installation-time
API/runtime interruptions remain outside this acceptance. Keep the initial Argo
CD credentials private; admin rotation and a tested Argo CD recovery backup
remain operational follow-up, not claims established here. Phase 7, after the
operator's next confirmation, is public application routing and TLS.

## Historical procedure archive

The 2026-10-24 manual rewrite preserves the previous procedural text separately:

- [Phase6 Gitops Procedures Archive](PHASE6_GITOPS_PROCEDURES_ARCHIVE.md)

Current operator entrypoint: [procedure index](../../runbooks/README.md).
