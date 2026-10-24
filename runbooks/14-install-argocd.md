# Install Argo CD and adopt application resources

**Where:** Reviewed infrastructure checkout on the management host.

**Order:** NONPROD, then PROD. Preserve application data and private Secrets.

## Preconditions

- [ ] Complete application/database checks in [runbook 13](13-deploy-application-manifests.md).
- [ ] Confirm desired manifests are available on remote infrastructure `main`.
- [ ] Use disabled automation for initial comparison; enable it after manual reconciliation.
- [ ] Keep PROD and both root Applications' automatic pruning disabled.

## 1. Select one cluster and install

Nonprod contains DEV/STAGE only; PROD contains PROD only.

- [ ] Start with nonprod. Select one cluster and inspect its API, nodes, and
      existing Argo CD namespace:

```sh
argocd_cluster=nonprod
case "$argocd_cluster" in
  nonprod) kubeconfig="$HOME/.kube/config-dev-stage" ;;
  prod) kubeconfig="$HOME/.kube/config-prod" ;;
  *) echo 'Choose nonprod or prod' >&2; exit 1 ;;
esac
export argocd_cluster kubeconfig
argocd_path="kubernetes/gitops/argocd/$argocd_cluster"
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes
kubectl --kubeconfig="$kubeconfig" get namespace argocd --ignore-not-found
```

- [ ] Confirm `192.168.77.11:6443` and `k3s-1-*` for nonprod, or
      `192.168.77.12:6443` and `k3s-2-*` for PROD. Review an existing
      installation before applying over it.

> [!WARNING]
> Stop on a cluster mismatch. Do not apply enabled policies to an
> unreviewed existing deployment.

Both installations use namespace `argocd` on independent clusters.

The [installation Kustomization](../kubernetes/gitops/argocd/install/kustomization.yaml)
pins the official upstream manifest to the v3.5.6 commit, with local resource
requests and memory limits. See [provenance](../kubernetes/gitops/argocd/install/UPSTREAM.md).
> [!NOTE]
> Do not use a moving `stable` URL or force resource ownership conflicts.

- [ ] Apply the pinned installation and cluster-specific settings; wait for
      the controller, server, and repository server:

```sh
kubectl --kubeconfig="$kubeconfig" apply -f kubernetes/gitops/argocd/install/namespace.yaml
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-argocd-bootstrap -k kubernetes/gitops/argocd/install
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-argocd-settings -f "$argocd_path/settings.yaml"
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status statefulset/argocd-application-controller --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status deployment/argocd-server --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd rollout status deployment/argocd-repo-server --timeout=1200s
kubectl --kubeconfig="$kubeconfig" -n argocd get deployments,statefulsets,pods,services
```

- [ ] Confirm Argo component Pods are Ready and application environments remain healthy. Public ingress must not expose Argo CD; its private Service uses the Admin VIP.

### If Argo CD startup is slow or fails

> [!NOTE]
> Allow slow image pulls and startup to finish. A missing `argocd-redis`
> Secret can occur until the Redis initialization container generates it.
> Investigate persistent errors, OOMs, restarts, or API interruptions; do
> not restart nodes merely because an initial rollout is slow.

## 2. Open private administration

- [ ] Configure Admin VIP access using [runbook 16, section 1](16-private-platform-access.md#1-configure-private-administrative-access).
- [ ] Open NONPROD `https://192.168.77.16:8080` or PROD `https://192.168.77.17:8080` through Tailscale.
- [ ] Authenticate as `admin` using that cluster's protected credentials.
- [ ] For an initial installation, retrieve the initial password only in a private terminal:

```sh
kubectl --kubeconfig="$kubeconfig" -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode
```

- [ ] After password rotation, use the replacement credential from the recovery kit.
- [ ] Preserve replacement access before removing the initial-admin Secret.

Argo CD serves native HTTPS. Validate the private endpoint's certificate identity
through the trusted administrative path; this certificate is independent of
public application certificates. Permanent access requires neither SSH tunnels
nor port-forward.

## 3. Publish and review before ownership changes

> [!NOTE]
> All sources must be this infrastructure repository, with local destination
> `https://kubernetes.default.svc`. The project restricts nonprod to
> `app-dev` and `app-stage`, and PROD to `app-prod`. The separate bootstrap
> project permits only Application and AppProject objects in local `argocd`.

- [ ] Confirm the selected GitOps manifests are on remote `main`; render the cluster-specific paths:

```sh
git rev-parse HEAD
git ls-remote origin refs/heads/main
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path"
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path/bootstrap"
```

### If remote `main` is behind

> [!WARNING]
> Local commits cannot be fetched by Argo CD. Finish installation and local
> validation, then stop before root bootstrap or syncing stale manifests.
> Publication requires operator authorization; do not push implicitly.

### Bootstrap child Applications for diff review

- [ ] For a fresh bootstrap, apply a reviewed local render of the child
      Applications with automation disabled. Use it to inspect Argo CD's
      repository comparison. Run `set -o pipefail` in the same Bash shell
      before this pipeline:

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

- [ ] In each private UI, hard-refresh every Application. Check its revision,
      rendered manifests, resource diff, namespace, digests, replicas, and
      one-worker backend command. Review tracking metadata for existing
      manually managed objects.

> [!WARNING]
> Stop on any unexplained difference. Do not sync a stale PROD command,
> recreate a PVC, or add existing Secrets to the desired resources.

The only expected deletion during first application sync is the completed
`prestart` hook Job: `BeforeHookCreation` replaces it, reruns idempotent migrations
from the same approved image, and `HookSucceeded` removes the successful hook.

- [ ] Review the expected `prestart` hook deletion explicitly. Record PVC
      UIDs, PV bindings, Pod UIDs, image IDs, and migration revision before
      and after adoption.

> [!NOTE]
> A missing `prestart` Job afterward is expected; loss of its database PVC
> is not. Adoption includes no new image/schema migration or database
> restore. Review backups and migrations separately for later schema changes.

## 4. Adopt manually, then review automation

- [ ] After remote revision and diffs are approved, manually sync each child
      once in its private UI: DEV → STAGE → PROD. Leave **pruning unchecked**
      and hooks enabled.
- [ ] Wait for successful operations and Synced/Healthy status. Confirm
      retained PVCs, unchanged application Pod specs, backend health, and
      private application login.

> [!NOTE]
> The API equivalent uses `strategy: {hook: {}}`. An `apply` strategy skips
> hooks and does not verify the prestart migration lifecycle. A local
> `kubectl apply` does not verify Argo CD ownership.

- [ ] Once the GitOps directories are published, create the root on the
      selected cluster:

```sh
kubectl --kubeconfig="$kubeconfig" kustomize "$argocd_path/bootstrap" |
  python3 scripts/kubernetes/render-manual-argocd-bootstrap.py |
  kubectl --kubeconfig="$kubeconfig" apply -f -
kubectl --kubeconfig="$kubeconfig" -n argocd get applications,appprojects
```

- [ ] Review and manually sync each root with pruning unchecked. Require
      only its project and expected child Applications in the desired output.

> [!WARNING]
> Stop if a root includes the other cluster's Applications or its own
> bootstrap directory. Roots have no cascading-delete finalizer. Deleting
> an Application is not rollback.

- [ ] After correct reconciliation, publish reviewed automation settings:
      `automated.enabled: true` and `selfHeal: true`.
- [ ] For nonprod, review managed resource inventory before enabling
      `prune: true`; retain `allowEmpty: false` and `PruneLast=true`.
      Keep PROD and root pruning disabled.

> [!WARNING]
> Do not enable pruning to clear an OutOfSync status. The PVC's
> `Prune=false,Delete=false` annotation does not protect a direct deletion.

## 5. Completion checks

- [ ] Confirm both private Argo CD UIs, intended local cluster destinations,
      successful root and child reconciliations, correct image IDs, healthy
      replicas, retained database PVC/PV bindings, and no unexpected deletion.
- [ ] After automation is enabled, test self-healing by temporarily changing
      only the non-secret `PROJECT_NAME` field in `backend-config`. Record
      its restoration by an automated operation.

> [!WARNING]
> Do not change credentials, image tags, replica counts, or data for the
> self-heal test. Do not delete data-bearing resources to test pruning.

- [ ] Record the selected revision, resource inventory and reconciliation results in the deployment/change record.

**Done when:** Roots and children are Synced/Healthy, expected image digests and PVC bindings are retained, and automation/pruning match the cluster policy.

**Stop:** Unexpected deletions, mismatched namespaces, failed hooks or database changes. Hold reconciliation and inspect the diff; do not delete an Application as a rollback method.

Official references: [installation](https://argo-cd.readthedocs.io/en/stable/getting_started/),
[declarative setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/),
[sync policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/), and
[hooks/waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

Use [runbook 15](15-publish-application.md) for public application routing and TLS. Keep Argo CD access private.
