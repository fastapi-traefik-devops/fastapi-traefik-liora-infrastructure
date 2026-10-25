# Hold delivery and reconnect the backend after database maintenance

**Where:** Management VM 200, infrastructure checkout; private Jenkins and
Argo CD UIs through Tailscale. Use only for an existing healthy environment.
**Data rule:** Keep all database/PVC contents and frontend/backend digests.

## 1. Record the exact starting state

- [ ] Select `dev`, `stage` or `prod`, its kubeconfig and Application name:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
environment=dev
case "$environment" in
  dev|stage) kubeconfig="$HOME/.kube/config-dev-stage"; root_app=liora-root-nonprod ;;
  prod) kubeconfig="$HOME/.kube/config-prod"; root_app=liora-root-prod ;;
  *) echo 'Choose dev, stage or prod' >&2; false ;;
esac
namespace="app-$environment"
child_app="app-$environment"
record=".local-work/private/db-maintenance/$environment-$(date -u +%Y%m%dT%H%M%SZ)"
umask 077
mkdir -m 700 -p "$record"
kubectl --kubeconfig="$kubeconfig" -n argocd get application "$root_app" -o json > "$record/root.json"
kubectl --kubeconfig="$kubeconfig" -n argocd get application "$child_app" -o json > "$record/child.json"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployment backend -o json > "$record/backend.json"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster.postgresql.cnpg.io liora-db -o json > "$record/cluster.json"
chmod 600 "$record"/*.json
```

- [ ] Record Jenkins enabled jobs, triggers, quiet state and queue in the
      private change record. Use `phase9-live-cycle.py status` as a read-only
      aid and inspect the Jenkins UI; do not infer approved schedules from
      examples. Record the existing backend container `imageID` and its
      desired digest from the selected overlay. Stop on an unexpected image.

## 2. Hold writes and reconciliation

- [ ] In Jenkins select **Prepare for Shutdown**, drain active builds and
      record/cancel queued requests. Disable only the jobs and schedules that
      could publish to this environment. Keep the exact original settings in
      the change record.
- [ ] Remove automatic sync from the selected root first, then its child:

```sh
kubectl --kubeconfig="$kubeconfig" -n argocd patch application "$root_app" \
  --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
kubectl --kubeconfig="$kubeconfig" -n argocd patch application "$child_app" \
  --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
kubectl --kubeconfig="$kubeconfig" -n argocd get application "$root_app" "$child_app" \
  -o jsonpath='{range .items[*]}{.metadata.name}{" automated="}{.spec.syncPolicy.automated}{"\n"}{end}'
```

**Stop:** If either Application is missing, a sync remains in flight, or a
different cluster is selected. Do not delete an Application to stop sync.

## 3. Complete database maintenance and reconnect

- [ ] Complete the selected database/operator change and wait for CNPG Ready.
      Confirm the primary and, on PROD, streaming standby on a separate node.
- [ ] If the backend must open fresh connections, prepare one annotation patch
      after the existing overlay patches. The helper stops if a patch already
      exists; review the existing file before another change:

```sh
change_id=$(date -u +%Y%m%dT%H%M%SZ)
bash scripts/local-python.sh scripts/kubernetes/prepare-db-reconnect.py \
  --environment "$environment" --change-id "$change_id"
```

The helper creates the following file and adds it to the selected
`kustomization.yaml`. Keep the existing image digests:

```yaml
# kubernetes/apps/liora/overlays/<environment>/db-reconnect-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  template:
    metadata:
      annotations:
        liora.aprt.info/db-reconnect: "<UTC change ID>"
```

```yaml
# Last entry under patches: in the selected kustomization.yaml
- path: db-reconnect-patch.yaml
```

- [ ] Render before committing. Compare the backend image, frontend image,
      Cluster/PVC definitions and only the intended annotation change with
      the recorded state. Publish through the normal reviewed Git path:

```sh
kubectl kustomize "kubernetes/apps/liora/overlays/$environment" > "$record/rendered.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployment backend \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
git diff -- "kubernetes/apps/liora/overlays/$environment"
```

Do not use `kubectl rollout restart`: Argo would reconcile an imperative
annotation away. Manually sync only the selected child without pruning, as in
[runbook 14, section 4](14-install-argocd.md#4-adopt-manually-then-review-automation).
Keep the root held. Wait for the backend rollout and compare its `imageID`
with the recorded digest:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/backend --timeout=10m
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pods -l app=backend \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

## 4. Verify and restore the recorded settings

- [ ] Log in through the canonical application HTTPS URL with the preserved
      user. Create, read, update and delete a disposable item. Readiness probes
      alone do not prove database authentication or writes.
- [ ] Restore the saved **child** `spec.syncPolicy`, then the saved **root**
      `spec.syncPolicy` using JSON Patch. This replaces the whole policy object
      exactly, including prune/selfHeal/retry options:

```sh
for pair in "child:$child_app" "root:$root_app"; do
  file="${pair%%:*}"
  app="${pair#*:}"
  patch=$(python3 - "$record/$file.json" <<'PY'
import json, sys
saved = json.load(open(sys.argv[1]))['spec']
if 'syncPolicy' in saved:
    print(json.dumps([{'op':'replace','path':'/spec/syncPolicy','value':saved['syncPolicy']}]))
else:
    print(json.dumps([{'op':'remove','path':'/spec/syncPolicy'}]))
PY
)
  kubectl --kubeconfig="$kubeconfig" -n argocd patch application "$app" \
    --type=json -p "$patch"
done
```

- [ ] Read back both Application policies and compare them with the saved
      JSON. Restore only the recorded Jenkins job/trigger settings, then
      release Jenkins quiet mode if it was not quiet before maintenance.
      Use [the job-policy release procedure](27-configure-jenkins-jobs.md#4-release-only-the-approved-policy)
      to check the allowlist and queue. Confirm Argo Synced/Healthy and
      repeat login/disposable CRUD.

**If interrupted or a check fails:** Keep Jenkins and Argo held. Preserve the
state record, patch and current PVCs. Resolve the database or login failure
before resuming; do not initialize empty data or change image digests.
