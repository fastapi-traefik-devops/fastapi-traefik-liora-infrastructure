# Historical procedure record — 14-install-argocd

Archived on 2026-10-24 before the operational-manual rewrite. This preserves
one-time decisions, commands, observations and original limitations. Statements
about current status describe their original checkpoint. Do not use this record
as the installation or incident-response entrypoint. Operator scripts remain
in their original locations.

Current procedure: [14-install-argocd.md](../../../../runbooks/14-install-argocd.md).

---

# Install separate Argo CD instances and adopt the application

**Where:** Reviewed infrastructure checkout on the management host.

> [!IMPORTANT]
> Run only during authorized Phase 6. Finish the publication and diff gates
> before syncing. Existing databases, Secrets and PVCs must survive adoption.
> The committed policies enable automation after verified adoption: nonprod
> children enable pruning; PROD and both roots keep pruning disabled. For a
> fresh installation, render a local bootstrap copy with
> `automated.enabled: false` until the gates below pass.

## 1. Select one cluster and install

Nonprod contains DEV/STAGE only; PROD contains PROD only.

- [ ] Start with nonprod. Select one cluster and inspect its API, nodes, and
      existing Argo CD namespace:

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

- [ ] Confirm `192.168.77.11:6443` and `k3s-1-*` for nonprod, or
      `192.168.77.12:6443` and `k3s-2-*` for PROD. Review an existing
      installation before applying over it.

> [!WARNING]
> Stop on a cluster mismatch. Do not apply enabled policies to an
> unreviewed existing deployment.

Both installations use namespace `argocd` on independent clusters.

The [installation Kustomization](../../../../kubernetes/gitops/argocd/install/kustomization.yaml)
pins the official upstream manifest to the v3.5.6 commit, with local resource
requests and memory limits. See [provenance](../../../../kubernetes/gitops/argocd/install/UPSTREAM.md).
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

- [ ] Confirm all seven component Pods are Ready and the three application
      environments remain healthy. Services must remain ClusterIP.

### If Argo CD startup is slow or fails

> [!NOTE]
> Allow slow image pulls and startup to finish. A missing `argocd-redis`
> Secret can occur until the Redis initialization container generates it.
> Investigate persistent errors, OOMs, restarts, or API interruptions; do
> not restart nodes merely because an initial rollout is slow.

## 2. Verify private UI access

- [ ] In a separate terminal, use the **same cluster selection** to open a
      loopback-only port forward:

```sh
kubectl --kubeconfig="$kubeconfig" -n argocd port-forward --address=127.0.0.1 service/argocd-server "$argocd_port:443"
```

- [ ] Reach the management port through a private SSH tunnel from the
      workstation. Use username `admin` and that cluster's initial password.

> [!NOTE]
> The bootstrap server certificate is self-signed; this private test does
> not verify public TLS. Each installation has independent Argo CD Secrets.

- [ ] In a private operator session, retrieve the selected cluster's initial
      password. Do not record it, put it in command arguments, or commit it:

```bash
# NONPROD
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode
printf '\n'

# PROD
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode
printf '\n'
```

### If the initial admin password was rotated

> [!NOTE]
> These commands read only the bootstrap password. Use replacement
> credentials from the protected recovery archive; the initial Secret may
> have been removed.

### Automated UI check (optional)

> [!TIP]
> With the Python/Playwright environment from runbook 13, the helper logs
> in through the UI and checks the authenticated session API. It reads the
> initial password in memory without saving authentication state.

- [ ] If using the automated alternative, run:

```sh
bash scripts/local-python.sh scripts/kubernetes/verify-argocd-ui.py
```

Standalone script: [Verify private Argo CD UI login](../../../../scripts/kubernetes/verify-argocd-ui.py).
Operators can copy this file and use their own prepared Python environment.
The helper accepts `argocd_cluster`, `kubeconfig`, and `argocd_port`; it uses a
three-minute browser timeout for this slow lab. The helper is only for initial
bootstrap; after rotating the admin password, use the private manual procedure.

### Preserve replacement access

- [ ] Keep the initial Secret until its password has been rotated and
      replacement access has been verified.

> [!NOTE]
> Argo CD bootstrap state is not part of the version 1 recovery YAML schema;
> this phase does not overwrite the existing recovery archive.

## 3. Publish and review before ownership changes

> [!NOTE]
> All sources must be this infrastructure repository, with local destination
> `https://kubernetes.default.svc`. The project restricts nonprod to
> `app-dev` and `app-stage`, and PROD to `app-prod`. The separate bootstrap
> project permits only Application and AppProject objects in local `argocd`.

- [ ] Confirm reviewed GitOps files and the verified PROD single-worker fix
      are on remote `main`; render the cluster-specific paths:

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

Standalone script: [Render manual Argo CD bootstrap](../../../../scripts/kubernetes/render-manual-argocd-bootstrap.py).
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

## 5. Acceptance and recovery boundaries

- [ ] Confirm both private Argo CD UIs, intended local cluster destinations,
      successful root and child reconciliations, correct image IDs, healthy
      replicas, retained database PVC/PV bindings, and no unexpected deletion.
- [ ] After automation is enabled, test self-healing by temporarily changing
      only the non-secret `PROJECT_NAME` field in `backend-config`. Record
      its restoration by an automated operation.

> [!WARNING]
> Do not change credentials, image tags, replica counts, or data for the
> self-heal test. Do not delete data-bearing resources to test pruning.

- [ ] Record completed and pending checks in
      `docs/testreports/phases/phase-06/REPORT.md` and the implementation plan.

> [!NOTE]
> Stop before Phase 7. Public routing, Argo CD external ingress,
> monitoring, and database replacement are separate phases.

Official references: [installation](https://argo-cd.readthedocs.io/en/stable/getting_started/),
[declarative setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/),
[sync policy](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/), and
[hooks/waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/).

After Phase 6 acceptance, [runbook 15](../../../../runbooks/15-publish-application.md) covers authorized
public application routing and TLS. Keep Argo CD access private.
