# Install separate Argo CD instances and adopt the application

**Where:** Reviewed infrastructure checkout on the management host.

Run only during authorized Phase 6. Finish the publication and diff gates before
syncing. Existing databases, Secrets and PVCs must survive adoption. The
committed policies now enable automation after verified adoption. Nonprod
children enable pruning; PROD and both roots keep pruning disabled. For a fresh
installation, render a local bootstrap copy with `automated.enabled: false` for
all Applications until the publication and diff gates below pass. Do not apply
the enabled policies to an unreviewed existing deployment.

## 1. Select one cluster and install

Nonprod contains DEV/STAGE only; PROD contains PROD only. Start with nonprod:

```sh
argocd_cluster=nonprod
case "$argocd_cluster" in
  nonprod) kubeconfig="$HOME/.kube/config-dev-stage"; argocd_port=18443 ;;
  prod) kubeconfig="$HOME/.kube/config-prod"; argocd_port=19443 ;;
  *) echo 'Choose nonprod or prod' >&2; exit 1 ;;
esac
export argocd_cluster kubeconfig argocd_port
argocd_path="kubernetes/gitops/argocd/$argocd_cluster"
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes
kubectl --kubeconfig="$kubeconfig" get namespace argocd --ignore-not-found
```

Require `192.168.77.11:6443` and `k3s-1-*` for nonprod, or
`192.168.77.12:6443` and `k3s-2-*` for PROD. Review an existing installation
before applying over it. Both use namespace `argocd` on independent clusters.

The [installation Kustomization](../kubernetes/gitops/argocd/install/kustomization.yaml)
pins the official upstream manifest to the v3.5.6 commit, with local resource
requests and memory limits. See [provenance](../kubernetes/gitops/argocd/install/UPSTREAM.md).
Do not use a moving `stable` URL or force resource ownership conflicts.

```sh
kubectl --kubeconfig="$kubeconfig" apply -f kubernetes/gitops/argocd/install/namespace.yaml
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-argocd-bootstrap -k kubernetes/gitops/argocd/install
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-argocd-settings -f "$argocd_path/settings.yaml"
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status statefulset/argocd-application-controller --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status deployment/argocd-server --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status deployment/argocd-repo-server --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd get deployments,statefulsets,pods,services
```

Allow slow image pulls and startup to finish. A missing `argocd-redis` Secret
can occur until the Redis initialization container generates it. Investigate
persistent errors, OOMs, restarts or API interruptions before proceeding; do not
restart nodes merely because an initial rollout is slow. Require all seven
component Pods Ready and the three application environments still healthy.
Services stay ClusterIP; no Ingress, LoadBalancer or NodePort is added.

## 2. Verify private UI access

In a separate terminal, with the same cluster selection:

```sh
kubectl --kubeconfig="$kubeconfig" -n argocd port-forward --address=127.0.0.1 service/argocd-server "$argocd_port:443"
```

Reach that management loopback port through a private SSH tunnel when using a
workstation browser. Initial credentials are username `admin` and the password
in that cluster's `argocd-initial-admin-secret`. Read it only in a private
operator session; do not record it, put it in command arguments or commit it.
The bootstrap server certificate is self-signed; this private test does not
verify public TLS. Each installation has independent Argo CD Secrets.

With the Python/Playwright environment from runbook 13, the automated alternative
logs in through the actual UI and verifies the authenticated session API. It
reads the initial password in memory and never saves authentication state:

```sh
"$HOME/liora-migration-tools/bin/python" scripts/kubernetes/verify-argocd-ui.py
```

Standalone script: [Verify private Argo CD UI login](../scripts/kubernetes/verify-argocd-ui.py).
Operators can copy this file and use their own prepared Python environment.
The helper accepts `argocd_cluster`, `kubeconfig`, and `argocd_port`; it uses a
three-minute browser timeout for this slow lab. The helper is only for initial
bootstrap; after rotating the admin password, use the private manual procedure.
Keep the initial Secret until its password has been rotated and the replacement
access is verified. Argo CD bootstrap state is not part of the version 1 recovery
YAML schema; this phase does not overwrite the existing recovery archive.

## 3. Publish and review before ownership changes

All sources must be this infrastructure repository, with local destination
`https://kubernetes.default.svc`. The project restricts nonprod to `app-dev` and
`app-stage`, and PROD to `app-prod`. The separate bootstrap project permits only
Application and AppProject objects in the local `argocd` namespace. No external
cluster credentials or old three-environment ApplicationSet are installed.

Confirm that reviewed GitOps files and the verified PROD single-worker fix are
on remote `main`. Local commits alone cannot be fetched by Argo CD. Publication
requires the operator's authorization; do not push implicitly during bootstrap.
If remote `main` is behind, finish installation and local validation, then stop
before root bootstrap or syncing any stale application manifests.

```sh
git rev-parse HEAD
git ls-remote origin refs/heads/main
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path"
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path/bootstrap"
```

For a fresh bootstrap, child Application definitions may be applied with
automation disabled in a reviewed local render to inspect
Argo CD's repository comparison, even before the root files are published:

```sh
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path" |
  python3 scripts/kubernetes/render-manual-argocd-bootstrap.py |
  kubectl --kubeconfig="$kubeconfig" apply -f -
kubectl --kubeconfig="$kubeconfig" -n argocd get applications
```

Standalone script: [Render manual Argo CD bootstrap](../scripts/kubernetes/render-manual-argocd-bootstrap.py).
This filter validates the entire rendered input before emitting manifests and
sets `enabled: false` and `prune: false` on every Application. It only accepts
Application/AppProject resources in `argocd`; it does not read credentials.
Use `set -o pipefail` in Bash to propagate any rendering failure.


In each private UI, hard-refresh each Application and review its revision,
rendered manifests and resource diff. Require the expected namespace, digests,
replicas and one-worker backend command. Existing manually managed objects need
tracking metadata. Inspect every other difference; do not sync a stale PROD
command or recreate a PVC. Existing Secrets are prerequisites outside these
Applications and must not be added to the desired resources.

The only expected deletion during first application sync is the completed
`prestart` hook Job: `BeforeHookCreation` replaces it, reruns idempotent migrations
from the same approved image, and `HookSucceeded` removes the successful hook.
Review this explicitly; a missing Job afterward is expected, while loss of its
database PVC is not. No new image/schema migration or database restore is part
of adoption. Record PVC UIDs, PV bindings, Pod UIDs, image IDs and migration
revision before and after. Subsequent image/schema changes need their own backup
and migration review.

## 4. Adopt manually, then review automation

Only after the remote revision and diffs are approved, sync each child once
through its private UI, with **pruning unchecked** and hooks enabled. The API
equivalent uses `strategy: {hook: {}}`; an `apply` strategy skips hooks and does
not verify the prestart migration lifecycle. Start DEV, then STAGE, then
PROD. Wait for successful operations, Synced/Healthy status, retained PVCs and
unchanged application Pod specs. Recheck health and private application login.
Do not treat a local `kubectl apply` as Argo CD ownership verification.

Once the GitOps directories are published, create the root on each cluster:

```sh
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path/bootstrap" |
  python3 scripts/kubernetes/render-manual-argocd-bootstrap.py |
  kubectl --kubeconfig="$kubeconfig" apply -f -
kubectl --kubeconfig="$kubeconfig" -n argocd get applications,appprojects
```

Review and manually sync each root with pruning unchecked. Its desired output
must contain only its project and the expected child Applications, never the
other cluster's applications or its own bootstrap directory. Roots deliberately
have no cascading-delete finalizer. Deleting an Application is not rollback.

Enable automation only through reviewed, published changes after correct
reconciliation: set `automated.enabled: true` and keep `selfHeal: true`.
For nonprod, separately review the managed resource inventory before enabling
`prune: true`; retain `allowEmpty: false` and `PruneLast=true`. PROD keeps
`prune: false`, including its root. Root pruning stays off until separately
reviewed. Do not enable pruning merely to clear an OutOfSync status. The PVC's
`Prune=false,Delete=false` annotation remains part of the application baseline;
it does not protect a direct operator deletion.

## 5. Acceptance and recovery boundaries

Require both private Argo CD UIs, only the intended local cluster destinations,
successful root and child reconciliations, correct image IDs, healthy replicas,
retained database PVC/PV bindings and no unexpected deletion. Test self-healing
by temporarily changing the non-secret `PROJECT_NAME` field in
`backend-config` after automation is enabled. Record its restoration by an
automated operation without changing credentials, image tags, replica counts or data.
Do not deliberately delete data-bearing resources to test pruning.

Record all completed and pending checks in `docs/testreports/PHASE6_REPORT.md`
and the implementation plan. Stop before Phase 7. Public routing, Argo CD
external ingress, monitoring and database replacement remain separate phases.

Official references: [installation](https://argo-cd.readthedocs.io/en/stable/getting_started/),
[declarative setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/),
[sync policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/), and
[hooks/waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

After Phase 6 acceptance, [runbook 15](15-publish-application.md) covers authorized
public application routing and TLS. Keep Argo CD access private.
