# Deploy application manifests

**Where:** Management VM 200, infrastructure repository root.
**Use for:** Fresh application deployment into empty environment namespaces.
**Order:** DEV → STAGE → PROD. Complete one environment before continuing.

## Preconditions

- [ ] Complete [K3s installation](09-install-k3s-clusters.md) and prepare the [operator tools](11-install-management-tools.md#operator-python-and-browser-tools).
- [ ] Select existing approved frontend/backend image digests; do not use placeholder tags.
- [ ] Confirm this is a fresh deployment. For existing data use [disaster recovery](../01-Disaster_recovery.md) or a reviewed GitOps update.
- [ ] Prepare private inputs using [recovery documentation](../recovery/README.md).
- [ ] Confirm the namespaces and database identities do not belong to another deployment.
- [ ] Install CNPG, cert-manager and Barman dependencies before applying their custom resources; see runbooks [18](18-cloudnative-pg.md) and [19](19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access).

## Environment reference

| Environment | Kubeconfig | Namespace | Hostname |
| --- | --- | --- | --- |
| DEV | `$HOME/.kube/config-dev-stage` | app-dev | dev.liora.aprt.info |
| STAGE | `$HOME/.kube/config-dev-stage` | app-stage | stage.liora.aprt.info |
| PROD | `$HOME/.kube/config-prod` | app-prod | liora.aprt.info |

## 1. Select and render one environment

- [ ] Select the environment and inspect its API, nodes and storage:

```sh
environment=dev
case "$environment" in
  dev) kubeconfig="$HOME/.kube/config-dev-stage"; hostname=dev.liora.aprt.info ;;
  stage) kubeconfig="$HOME/.kube/config-dev-stage"; hostname=stage.liora.aprt.info ;;
  prod) kubeconfig="$HOME/.kube/config-prod"; hostname=liora.aprt.info ;;
  *) echo 'Choose dev, stage, or prod' >&2; exit 1 ;;
esac
namespace="app-$environment"
overlay="kubernetes/apps/liora/overlays/$environment"
render_dir="$PWD/.local-work/render/$environment"
recovery_dir="$PWD/recovery"
export environment kubeconfig namespace render_dir recovery_dir hostname
umask 077
mkdir -p "$render_dir"
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
kubectl --kubeconfig="$kubeconfig" get storageclass
kubectl --kubeconfig="$kubeconfig" kustomize "$overlay" > "$render_dir/all.yaml"
python3 scripts/kubernetes/split-application-render.py
```

Standalone script: [split-application-render.py](../scripts/kubernetes/split-application-render.py).

- [ ] Match NONPROD to API `.11:6443` and `k3s-1-*`; match PROD to `.12:6443` and `k3s-2-*`.
- [ ] Require all nodes Ready and `local-path` available.
- [ ] Inspect rendered images, environment configuration, Secret references, replicas and namespace.
- [ ] Confirm four output groups: `config-storage.yaml`, `database.yaml`, `prestart.yaml`, `application.yaml`.

**Stop:** Wrong API/node identity, missing storage, failed render or an unconfigured image.

## 2. Prepare namespace, credentials and storage

### Create the selected namespace

After selecting and verifying the environment in section 1, create its
namespace if it does not exist. This step is also used before the backup
provisioner; stop here and return to the scenario checklist when preparing all
three namespaces ahead of application deployment.

- [ ] Create or confirm the selected namespace:

```sh
kubectl --kubeconfig="$kubeconfig" create namespace "$namespace" --dry-run=client -o yaml |
  kubectl --kubeconfig="$kubeconfig" apply -f -
```

### Provision fresh application credentials

- [ ] Validate private inputs:

```sh
RECOVERY_DIR="$recovery_dir" bash recovery/check_credentials.sh --all --offline
```

- [ ] Review named-field warnings without deleting private data. Resolve errors before continuing.
- [ ] Confirm recovery files are ignored, access-restricted and stored in the off-host recovery kit.
- [ ] Create fresh application Secrets only after confirming the namespace and
      private inputs belong to this empty environment:

```sh
python3 scripts/kubernetes/bootstrap-application-secrets.py
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get secrets
```

Standalone script: [bootstrap-application-secrets.py](../scripts/kubernetes/bootstrap-application-secrets.py).

The helper refuses existing application Secrets or PVCs. It creates
`backend-secrets`, `db-secrets` and `ghcr-pull-secret` without logging values.
Do not use it to rotate credentials or restore an existing database account.

- [ ] Provision derived CNPG credentials using [runbook 18](18-cloudnative-pg.md#2-provision-database-credentials).
- [ ] Confirm the Barman plugin and this environment's R2 Secret exist.
      If absent, complete [backup access setup](19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access)
      before database startup.
- [ ] Confirm the DNS credential and issuer exist. If absent, complete
      [certificate preparation](15-publish-application.md#2-dns-and-certificate-prerequisites).

```sh
kubectl --kubeconfig="$kubeconfig" -n cnpg-system get deployment barman-cloud
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get secret r2-backup
kubectl --kubeconfig="$kubeconfig" -n cert-manager get secret cloudflare-dns-token
kubectl --kubeconfig="$kubeconfig" get clusterissuer letsencrypt-cloudflare
```
- [ ] Check that no `liora-storage-check` Pod/PVC already exists, then create the storage probe:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pod,pvc liora-storage-check --ignore-not-found
```

- [ ] Only when neither name exists, run:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" create -f runbooks/_resources/application-storage-check.yaml
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Bound pvc/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" logs liora-storage-check
probe_pv=$(kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc liora-storage-check -o jsonpath='{.spec.volumeName}')
kubectl --kubeconfig="$kubeconfig" get pv "$probe_pv" -o wide
```

- [ ] Require the expected namespace marker and node placement.
- [ ] Remove only the probe and its recorded PV:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" delete pod/liora-storage-check pvc/liora-storage-check --wait=true
kubectl --kubeconfig="$kubeconfig" wait --for=delete "pv/$probe_pv" --timeout=180s
```

## 3. Bring up PostgreSQL, then prestart

- [ ] Apply configuration and database resources in the selected namespace:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/config-storage.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/database.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=condition=Ready cluster/liora-db --timeout=600s
expected_instances=1
if [ "$environment" = prod ]; then expected_instances=2; fi
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.readyInstances}'="$expected_instances" cluster/liora-db --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster,pvc -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get job prestart --ignore-not-found
```

- [ ] Require all database PVCs Bound and PROD instances on different nodes.
- [ ] Confirm no previous `prestart` Job exists for this fresh installation.
- [ ] Apply initialization and wait for completion:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/prestart.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=condition=complete job/prestart --timeout=660s
```

**Stop:** On failed initialization, inspect Job events/logs privately and correct the cause. Do not delete database PVCs. Direct `kubectl apply` does not execute Argo hook ordering; do not apply the unsplit overlay as a shortcut.

## 4. Start application workloads

- [ ] Start the application only after initialization completes:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/application.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/backend --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/frontend --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/adminer --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployments,pods,pvc,ingress -o wide
```

## 5. Check application access

- [ ] Complete [routing and TLS](15-publish-application.md) before HTTPS checks.
- [ ] Check the canonical hostname through the private edge with normal TLS validation:

```sh
curl --fail --silent --show-error --resolve "$hostname:443:192.168.77.240" "https://$hostname/api/v1/utils/health-check/"
curl --fail --silent --show-error --resolve "$hostname:443:192.168.77.240" --output /dev/null "https://$hostname/"
acceptance_url="https://$hostname" acceptance_address=192.168.77.240 acceptance_cleanup=true bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
```

Standalone script: [verify-application-ui.py](../scripts/kubernetes/verify-application-ui.py).

- [ ] Require login, disposable create/read/update, persistence after reload, deletion and subsequent absence.
- [ ] Alternatively perform those actions manually at the canonical HTTPS URL from an authorized browser.
- [ ] Record the infrastructure revision, selected/running image digests, PVC bindings and application results without credentials.
- [ ] Check the public URL from outside the private network. A private-edge check does not cover the public path.
- [ ] Complete [GitOps adoption](14-install-argocd.md) before handing deployments to Argo CD.

**Done when:** Database and application checks pass in each isolated environment, actual image IDs match the selected pair, HTTPS works, and only disposable check items were removed.

## Updates and recovery

- [ ] For GitOps-owned environments, change reviewed Git state and use Argo hooks; do not repeat fresh Secret/database initialization.
- [ ] Before schema changes, review the recovery point and compatibility of the selected image pair.
- [ ] For data restoration, follow [disaster recovery](../01-Disaster_recovery.md).
- [ ] For a recovery exercise, use [isolated PITR verification](../docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md).
- [ ] Roll back application images through Git. An image rollback does not undo database migrations.
