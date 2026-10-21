# Phase 6 report — independent Argo CD instances

Status on 2026-10-21: **in progress**, pending publication and root/automation
verification. Do not start Phase 7.

## Implementation and provenance

Worktree `/home/root-admin/liora-argocd-phase6`, branch
`migration/liora-phase6`, based on original main `206b394`. The operator's newer
runbook readability commit `0588b5a` was merged without changing its contents.
No push has been performed by this phase.

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
All child/root definitions have `automated.enabled: false`, `prune: false` and
no cascading-delete finalizers during adoption. Self-healing is configured but
inactive while automation is disabled.

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

Root definitions are locally rendered and ready, with a separate bootstrap
project restricted to Application/AppProject objects in local argocd. Roots
source only their own cluster directory, excluding bootstrap and installation.
They have not yet been applied: remote main does not contain these new GitOps
paths. Root reconciliation and automation/self-heal tests remain pending an
explicit authorization to publish. PROD pruning will remain disabled; enabling
nonprod pruning requires a separate inventory review after root reconciliation.

## Validation and local evidence

YAML parsing, all project/root Kustomize renders, Python syntax and runbook shell
syntax passed. Historical selected blobs, filtered history and GitOps files
passed Gitleaks with no findings. Evidence is under
`/home/root-admin/liora-phase6-artifacts/`, including adoption UID snapshots and
`adoption-results.json`, `hook-adoption-results.json` and
`hook-adoption-before.json`. Evidence contains result metadata and no credentials.

`runbooks/14-install-argocd.md` documents installation, private access, publication,
diff review, hook-aware manual sync, root bootstrap, automation and pruning gates.
The UI helper is linked directly under its command. Original recovery files,
Terraform state and unrelated untracked operator documents are not modified.

## Remaining work

1. Complete: hook-enabled adoption and private application login/health checks.
2. Publish the reviewed GitOps commits only after operator authorization.
3. Apply and reconcile each root against the published revision.
4. Enable reviewed automation, verify harmless self-healing and review nonprod
   pruning; leave PROD pruning off.
5. Record final image/PVC/health results, stop private forwards and finish this
   report and the plan before Phase 7.
