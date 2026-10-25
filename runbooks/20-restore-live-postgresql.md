# Restore live PostgreSQL data

**Where:** Management VM 200 or a replacement trusted operator machine; infrastructure repository root.
**Use for:** Rebuild an application environment from an R2 physical backup and archived WAL.
**Order:** DEV → STAGE → PROD; finish one environment before starting another.

## Preconditions

- [ ] Complete the infrastructure/platform portion of [disaster recovery](../01-Disaster_recovery.md). Install CNPG, cert-manager and Barman using [18](18-cloudnative-pg.md) and [19](19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access).
- [ ] Recover the matching private application/database credentials, GHCR access and R2 inputs using [recovery documentation](../recovery/README.md). Use credentials valid at the selected recovery point.
- [ ] Recover the application revision and immutable frontend/backend image pair compatible with that database's Alembic revision. Keep the previous pair in the incident record.
- [ ] Hold Jenkins publication/promotion and Argo reconciliation using [24](24-hold-surviving-automation.md). On replacement clusters, leave application root/child Applications uninstalled or disabled. Finish in-flight work first.
- [ ] Confirm the target namespace has no CNPG `liora-db`, PVCs, running application Deployments or active Jobs. This procedure creates a replacement; it does not erase or restore over a live database.
- [ ] If recovering Kubernetes metadata using [21](21-restore-k3s-etcd-snapshot.md), resolve its storage gate first. Existing recovered Cluster/PVC objects are not an empty target.
- [ ] Prepare [operator Python](11-install-management-tools.md#operator-python-and-browser-tools), `kubectl`, private kubeconfigs and a normal reviewed GitOps write path.

**Stop:** A source database is still accepting writes under the intended identity, automation cannot be held, credentials/history are unavailable, or replacement storage is insufficient. Fence the old environment before publishing the replacement endpoint. Do not delete its data to satisfy an empty-target check.

## 1. Select the environment and recovery point

- [ ] Set environment variables; substitute the incident's UTC recovery point and unique recovery identity:

```sh
environment=dev
case "$environment" in
  dev) kubeconfig="$HOME/.kube/config-dev-stage"; hostname=dev.liora.aprt.info ;;
  stage) kubeconfig="$HOME/.kube/config-dev-stage"; hostname=stage.liora.aprt.info ;;
  prod) kubeconfig="$HOME/.kube/config-prod"; hostname=liora.aprt.info ;;
  *) echo 'Select dev, stage, or prod' >&2; exit 1 ;;
esac
namespace="app-$environment"
recovery_dir="$PWD/recovery"
restore_dir="$recovery_dir/live-restore/$environment-incident-1"
recovery_id=incident-1
export environment kubeconfig namespace recovery_dir hostname
umask 077
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
kubectl --kubeconfig="$kubeconfig" get storageclass
```

- [ ] Match NONPROD to `.11:6443` and `k3s-1-*`, PROD to `.12:6443` and `k3s-2-*`. Require Ready nodes and `local-path` storage. PROD needs two different eligible nodes.
- [ ] Catalog physical backups directly from R2; Kubernetes Backup resources are not required:

```sh
bash scripts/local-python.sh scripts/backups/prepare-live-restore.py catalog \
  --environment "$environment"
```

Standalone tool: [prepare-live-restore.py](../scripts/backups/prepare-live-restore.py).

- [ ] Select a `DONE` physical `backup_id` whose **end time precedes the target**. Use an explicit timezone. Confirm the target precedes the unwanted change and is covered by retained WAL. A base-backup listing alone does not establish WAL coverage.
- [ ] Record source destination, archive server, physical backup ID, target, incident identity and image pair. Do not record passwords.

```sh
backup_id=20261025T020149
recovery_target=2026-10-25T03:00:00Z
```

These assignments illustrate the format; replace both with the incident selection.
After an earlier recovery, use that archive's recorded `--source-destination` and
`--source-server` on **both** catalog and prepare commands if they differ from
the current overlay. Never infer an old archive identity from the environment name.

## 2. Prepare credentials and the replacement bundle

- [ ] Create the selected empty namespace following [13, namespace preparation](13-deploy-application-manifests.md#2-prepare-namespace-credentials-and-storage). Do not apply its fresh database manifests or prestart Job.
- [ ] Restore matching Secrets through the private recovery procedure. For a new namespace, the existing application Secret helper can materialize the recovered values:

```sh
bash scripts/local-python.sh scripts/kubernetes/bootstrap-application-secrets.py
bash scripts/local-python.sh scripts/kubernetes/bootstrap-cnpg-secrets.py \
  --kubeconfig "$kubeconfig" --environment "$environment"
```

Standalone tools: [application Secrets](../scripts/kubernetes/bootstrap-application-secrets.py), [CNPG Secrets](../scripts/kubernetes/bootstrap-cnpg-secrets.py).

- [ ] Require the recovered database password to match the backup's `app_owner` account. Do not generate a replacement password or run `initdb`. CNPG uses `cnpg-superuser` for administrative access; application ownership comes from the physical backup.
- [ ] Prepare the bundle and create only the selected environment's missing R2 Secret:

```sh
bash scripts/local-python.sh scripts/backups/prepare-live-restore.py prepare \
  --environment "$environment" --kubeconfig "$kubeconfig" \
  --backup-id "$backup_id" --target-time "$recovery_target" \
  --recovery-id "$recovery_id" --output "$restore_dir" --provision-r2
```

Standalone tool: [prepare-live-restore.py](../scripts/backups/prepare-live-restore.py).

The tool refuses an existing target Cluster/PVC, active writers, mismatching R2
Secrets, future/timezone-free targets, incomplete backups and a nonempty new
archive destination. It does not deploy a database. Errors stop with exit 1;
existing files and resources remain intact. Use a new output directory after
investigating any partial preparation.

- [ ] Review `database.yaml`, `maintenance.yaml`, `application.yaml`, `prestart.yaml` and `gitops-patches/` privately. Require the pinned PostgreSQL image, original storage/resources, unchanged application digests, one DEV/STAGE instance and two PROD instances with required node anti-affinity.
- [ ] Require distinct archives:

| Purpose | Destination | Archive server | Retention |
| --- | --- | --- | --- |
| Read source | Selected incident archive | Selected original identity | None on `restore-source` |
| New writes | `s3://liora-backup/<env>/recovery-<recovery-id>/` | `liora-<env>-r-<recovery-id>` | Existing environment recovery window |

The source ObjectStore has no retention cleanup. The recovered Cluster writes
WAL and future base backups only to the new destination. Keep the source archive
until its incident/recovery retention decision; do not add independent age-based
R2 deletion rules. Credentials remain bucket-scoped, not prefix-isolated.

## 3. Restore the database with application writes held

- [ ] Apply configuration with all application Deployments at zero, then **create** the replacement database resources:

```sh
kubectl --kubeconfig="$kubeconfig" apply -f "$restore_dir/maintenance.yaml"
kubectl --kubeconfig="$kubeconfig" create -f "$restore_dir/database.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait \
  --for=condition=Ready cluster.postgresql.cnpg.io/liora-db --timeout=30m
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster,pods,pvc -o wide
```

- [ ] If the restore cannot reach its target, retain resources, logs and the source archive. Keep writers, prestart and reconciliation off. Do not remove the recovery target, substitute `initdb`, or silently accept an earlier point.
- [ ] Verify the primary, database and restored schema:

```sh
primary=$(kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster liora-db \
  -o jsonpath='{.status.currentPrimary}')
kubectl --kubeconfig="$kubeconfig" -n "$namespace" exec "$primary" -c postgres -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d app -c \
  "SELECT current_database(), pg_is_in_recovery(), current_setting('server_version');
   SELECT datname,pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname='app';
   SELECT version_num FROM alembic_version;
   SELECT extname FROM pg_extension;
   SELECT tablename,tableowner FROM pg_tables WHERE schemaname='public';"
```

- [ ] Require primary out of recovery, database `app`, owner/table owner `app_owner`, required `uuid-ossp` extension and migration revision compatible with the selected application images.
- [ ] Inspect incident-specific business records around the chosen recovery point. Confirm intended data is present and the unwanted change absent. Record counts/identifiers without exporting sensitive contents.
- [ ] Confirm `cnpg-app` password authentication, `POSTGRES_USER=app_owner`, `POSTGRES_DB=app` and stable `POSTGRES_SERVER=db` configuration. Keep Adminer on the same endpoint.
- [ ] For PROD, require two Ready instances on different nodes, one primary/one streaming standby, and no synchronous replication configuration. Inspect `pg_stat_replication` on the primary.

## 4. Reconcile desired state before opening application traffic

- [ ] Add the generated recovery configuration to the selected overlay:

```sh
bash scripts/local-python.sh scripts/backups/install-recovery-overlay.py \
  --environment "$environment" --bundle "$restore_dir"
kubectl kustomize "kubernetes/apps/liora/overlays/$environment" > "$restore_dir/reconciled.yaml"
```

Standalone tool: [install-recovery-overlay.py](../scripts/backups/install-recovery-overlay.py).

The tool adds the source resource and appends recovery patches **after** the
existing overlay patches. It preserves other overlay settings. It refuses an
existing `recovery/` directory or changed application image pair. If either check
fails, stop and review the existing recovery configuration or concurrent update;
do not delete it to force installation.
- [ ] Render the overlay and compare its Cluster/ObjectStores to `database.yaml`. Require recovery bootstrap, the read-only source identity and new writable destination. Confirm all existing application digests remain unchanged.
- [ ] Review and commit only the selected recovery configuration using normal repository rules; publish it before enabling Argo. Preserve concurrent image/configuration updates. Root Applications must still remain held.
- [ ] Run the compatible initialization/Alembic Job once, after database readiness and schema review:

```sh
kubectl --kubeconfig="$kubeconfig" create -f "$restore_dir/prestart.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait \
  --for=condition=complete job/prestart --timeout=10m
```

- [ ] If a Job named `prestart` already exists, inspect it. Do not delete an active Job or use a failed migration as permission to initialize an empty database. Keep the selected application version compatible with the recovered schema.
- [ ] Start fresh application Pods with the preserved digests. This also establishes new SQLAlchemy connections:

```sh
kubectl --kubeconfig="$kubeconfig" apply -f "$restore_dir/application.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/backend --timeout=10m
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/frontend --timeout=10m
curl --fail --show-error --max-time 30 "https://$hostname/"
```

- [ ] Log in using the recovered application credentials. Create, read, update and delete one disposable record through the application. Confirm HTTPS and actual Pod image IDs, not only readiness probes. Keep diagnostic output private.
- [ ] Compare live resources with the published recovery overlay; then restore the exact prior approved Argo/Jenkins policies using [14, Argo policy release](14-install-argocd.md#4-adopt-manually-then-review-automation) and [17, Jenkins activation](17-migrate-jenkins-ci.md#4-activate-delivery). Require Argo `Synced/Healthy`. During full disaster recovery, keep these holds until the navigator reaches its release step. Leave unrelated jobs disabled and PROD image promotion blocked by its acceptance gate.

## 5. Restore backup operations and close the incident

- [ ] Follow [19](19-cnpg-r2-backup-pitr.md): verify new WAL objects, perform a coordinated base backup, verify monitoring and the VM 250 timer. Do not start an overlapping backup cycle.
- [ ] Confirm backup/PITR tools select the active ObjectStore and archive server after handover.
- [ ] Add the new archive identity, Git commit, image pair, recovery point, database/app checks and elapsed recovery time to the incident report and private recovery kit.
- [ ] Preserve the source archive and fenced original resources until the incident owner authorizes retirement. Do not delete unrelated PVCs, namespaces or Secrets.

**Complete:** Restored data and ownership match the selected recovery point;
application login/CRUD and HTTPS work; PROD replication is healthy; GitOps owns
the recovered configuration; approved automation and backup operations are
restored. The [isolated PITR exercise](../docs/operations/POSTGRESQL_BACKUP_VERIFICATION.md)
is a separate verification procedure and never switches live endpoints.

## References

- [CNPG Barman recovery configuration](https://cloudnative-pg.io/plugin-barman-cloud/docs/usage/)
- [CNPG recovery targets](https://cloudnative-pg.io/docs/1.30/recovery/)
