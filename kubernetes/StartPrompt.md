You are working in the infrastructure repository
fastapi-traefik-liora-infrastructure. You have its committed contents and
kubernetes/IMPLEMENTATION_PLAN.md. Do not assume that any other uncommitted
files from earlier work are available. Ensure the supplied
kubernetes/IMPLEMENTATION_PLAN.md is available in your isolated worktree;
uncommitted files do not carry over to a new worktree automatically.

Context:
- Proxmox hosts two K3s clusters. DEV and STAGE use VMs 201–203, API VIP
  192.168.77.11, and separate app-dev/app-stage namespaces. PROD uses VMs
  211–213, API VIP 192.168.77.12, and app-prod.
- The application source is
  `https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application`.
  A local copy is at `../fastapi-traefik-liora-application/`; verify its Git
  remote and HEAD before using it. Treat the application repository as
  read-only.
- The immediate goal is to run the application's current deployment with
  minimal changes. PostgreSQL, Adminer, and the prestart Job remain in the
  initial deployment. Argo CD, public routing, monitoring, CloudNativePG,
  and CI migration come later.
- All repository documentation and code comments must be in English.
- Live credentials, private keys, and Terraform state must never be committed.

Cluster access on management VM 200 as `root-admin`:
- DEV/STAGE: `$HOME/.kube/config-dev-stage` (nodes `k3s-1-01`,
  `k3s-1-02`, `k3s-1-03`).
- PROD: `$HOME/.kube/config-prod` (nodes `k3s-2-01`, `k3s-2-02`,
  `k3s-2-03`).
- All six nodes were last reported Ready on K3s `v1.36.5+k3s1`; verify
  current status instead of assuming this observation is still current.
- Do not run unqualified `kubectl`: its default context points to a
  different test cluster. Use the explicit kubeconfig for every
  cluster-dependent command, including examples in the runbook:
  `kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get nodes` or
  `kubectl --kubeconfig="$HOME/.kube/config-prod" get nodes`.
  For local rendering, use `kustomize build` if available or specify the
  intended kubeconfig with `kubectl kustomize`.
- Interactive aliases already defined in VM 200's `.bashrc` are
  `k1='kubectl --kubeconfig="/home/root-admin/.kube/config-dev-stage"'`
  and `k2='kubectl --kubeconfig="/home/root-admin/.kube/config-prod"'`.
  They are conveniences only; use explicit kubeconfig paths in documentation
  and scripts.

Read first:
1. README.md and docs/ARCHITECTURE.md in this repository.
2. The entire kubernetes/IMPLEMENTATION_PLAN.md, including both the target
   architecture and implementation order.
3. The relevant cluster runbooks, especially VM provisioning and K3s
   installation.
4. The application repository's current deploy/base/ and
   deploy/overlays/{dev,stage,prod}/. Record the exact source commit you read.
   Treat its historical k8s/ tree as reference material, not the deployment
   source.

The scope is Phase 0 and Phase 1 only. Start with Phase 0; do not begin
Phase 1 until I confirm after its report. Document the later deployment
procedure in the new runbook during Phase 1, but do not execute Phase 2 or
later:
- Compare the plan with what is actually committed in this repository and
  with the current application manifests.
- Identify the minimum files and compatibility changes needed to render the
  three existing application overlays in this repository.
- Import the current deployment and its selected Git history into
  kubernetes/apps/liora/ while preserving existing components and behavior.
  Do not redesign the application or introduce target-state platform
  components yet.
- Render DEV, STAGE, and PROD locally and inspect namespaces, image
  references, replicas, Secret dependencies, PVCs, and Ingress hosts.
- PROD currently has placeholder image tags. Do not invent a release or
  silently choose a PROD digest. If no approved digest is available, finish
  independent work and ask me which existing release to use. You may render
  PROD to inspect its structure with placeholders, but do not mark Phase 1
  complete until approved real digests are in place.

At the end of each phase:
- Update `kubernetes/IMPLEMENTATION_PLAN.md` to reflect what was actually
  completed and what remains; do not mark unverified work as complete.
- Give me a short report covering:
  - Exact files added or changed and why.
  - The application source commit used.
  - Render results and any remaining blockers.
  - Which checklist items in this phase are complete, and which require
    access to the live clusters or my decision.
- Propose the next small actions, then stop and wait for my confirmation
  or clarification before beginning the next phase.

Do not create namespaces, restore Secrets, apply manifests, or change a live
cluster. Do not merge into the current branch or push. We will verify this
small increment before proceeding.
Do not modify the application repository. Create
kubernetes/APPLICATION_REPOSITORY_CLEANUP.md in the infrastructure repository
to list application-repository paths that may be removed after the migration
has been fully tested. Do not delete those paths now. The goal is to separate
the application and infrastructure repositories.

Additional requirements for this first increment:

1. Continue the runbooks alongside implementation. After the existing
   "Install K3s on both clusters" step, add step 10 to both
   00-Installation_from-0.md and 01-Disaster_recovery.md. Link it to a new
   runbook, runbooks/13-deploy-application-manifests.md. Runbook filenames
   10–12 already have other purposes; do not rename them for this step.

2. The new runbook must describe the actual deployment procedure for the
   manifests introduced in this increment: cluster context selection,
   namespace and Secret prerequisites, rendering, application order,
   PostgreSQL and prestart Job checks, and separate DEV/STAGE/PROD acceptance
   checks. Explain that applying manifests to a fresh recovery cluster does
   not restore application data; data restoration needs its own procedure.
   Do not claim that live deployment has been verified until it has been run.

3. Preserve the Git history of files migrated from the application repository.
   Do not merely download or copy files into a new commit. Investigate a
   selective history import, for example with git-filter-repo in a disposable
   clone, followed by an unrelated-history merge and Git moves to the final
   paths. Preserve author and commit history as far as practical, document
   the source repository and source commit, and verify that historical
   changes to imported files remain discoverable. Check the selected history
   for credentials before importing it. If credentials are found, stop that
   history import and report the affected paths and options without exposing
   the values.

4. Import only the application-owned deployment files needed for this
   increment. Apply the same history-preserving approach to other relevant
   infrastructure files when their later phases begin. Do not import the
   entire application repository or its historical k8s/ tree just to retain
   history.

5. Perform the history import on an isolated migration branch or worktree.
   Ensure the supplied implementation plan is available there. Import
   commits are permitted on that branch because they preserve history. Do
   not merge them into the current branch or push before we review and test
   the increment. Do not change a live cluster during this increment.
