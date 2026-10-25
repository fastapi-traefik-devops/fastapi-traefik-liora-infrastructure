# Install CloudNativePG databases

**Where:** Management VM 200, infrastructure repository root.
**Use for:** Install the CNPG operator in either scenario; sections 2–4
initialize and verify empty databases on a new installation only.
**Order:** DEV → STAGE → PROD. Complete each environment before continuing.

## Preconditions

- [ ] Complete [K3s installation](09-install-k3s-clusters.md).
- [ ] For operator installation, select one cluster's kubeconfig in the command below, then repeat for the other cluster. For fresh database creation, select the environment and export its variables in [runbook 13](13-deploy-application-manifests.md#1-select-and-render-one-environment).
- [ ] Before sections 2–4 on a fresh installation, confirm the target namespace has no application database or data-bearing PVCs and provision `backend-secrets`, `db-secrets` and registry access using runbook 13.
- [ ] For data recovery, complete section 1 only, then return to the [disaster recovery procedure](../01-Disaster_recovery.md). Do not initialize an empty database in place of a restore.
- [ ] Reserve resources for the database, backup sidecar and operators.

## Configuration reference

| Environment | Namespace | Instances | PVC per instance | CPU request / limit | Memory request / limit |
| --- | --- | --- | --- | --- | --- |
| DEV | app-dev | 1 | 2 GiB | 250m / 1 | 512 MiB / 1 GiB |
| STAGE | app-stage | 1 | 2 GiB | 250m / 1 | 512 MiB / 1 GiB |
| PROD | app-prod | 2 | 2 GiB | 250m / 1 | 512 MiB / 1 GiB |

PostgreSQL 16 and operator images are pinned in the
[operator installation](../kubernetes/platform/cloudnative-pg/kustomization.yaml)
and application components. PROD uses asynchronous streaming replication and
required placement on different nodes. Local-path PVC requests are not filesystem
quotas; data and WAL share the backing filesystem.

| Purpose | Configuration |
| --- | --- |
| Application endpoint | `db:5432` |
| Database / owner | `app` / `app_owner` |
| Application bootstrap Secret | `cnpg-app` |
| Administrative role / Secret | `postgres` / `cnpg-superuser` |
| Required extension | `uuid-ossp` |

## 1. Install the operator

- [ ] Check the selected API and node identities.
- [ ] Install independently in NONPROD and PROD:

```sh
kubeconfig="$HOME/.kube/config-dev-stage"  # Repeat with config-prod after NONPROD succeeds.
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-cnpg-platform -k kubernetes/platform/cloudnative-pg
kubectl --kubeconfig="$kubeconfig" -n cnpg-system rollout status deployment/cnpg-controller-manager --timeout=600s
```

- [ ] Install cert-manager and the Barman plugin using [runbook 19, section 1](19-cnpg-r2-backup-pitr.md#1-install-backup-dependencies-and-access) before applying database manifests that request the backup plugin.

## 2. Provision database credentials

- [ ] Confirm the selected environment's private recovery inputs match its application Secrets.
- [ ] Create the derived CNPG Secrets:

```sh
bash scripts/local-python.sh scripts/kubernetes/bootstrap-cnpg-secrets.py --kubeconfig "$kubeconfig" --environment "$environment"
```

Standalone script: [bootstrap-cnpg-secrets.py](../scripts/kubernetes/bootstrap-cnpg-secrets.py).

The helper derives `app_owner` and administrative credentials from the existing
environment database password. It refuses conflicting existing CNPG credentials.
Do not rotate passwords by editing a Secret alone.

## 3. Create and initialize the database

- [ ] Follow [runbook 13, section 3](13-deploy-application-manifests.md#3-bring-up-postgresql-then-prestart)
      for the exact apply order and readiness checks.

Argo CD uses database readiness at wave -2, prestart at wave 0 and application
workloads at wave 1. The fresh database initialization creates the application
administrator from the environment's initialization credentials.

## 4. Verify database and application

- [ ] Inspect Cluster state, instance placement and PVC bindings:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster,pods,pvc -o wide
primary=$(kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster liora-db -o jsonpath='{.status.currentPrimary}')
kubectl --kubeconfig="$kubeconfig" -n "$namespace" exec "$primary" -c postgres -- psql -U postgres -d app -c 'SELECT current_database(), pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname = current_database();'
kubectl --kubeconfig="$kubeconfig" -n "$namespace" exec "$primary" -c postgres -- psql -U postgres -d app -c 'SELECT extname FROM pg_extension; SELECT version_num FROM alembic_version;'
```

- [ ] Require database `app`, owner `app_owner`, `uuid-ossp` and the migration revision required by the selected backend image.
- [ ] For PROD, require two Ready instances on different nodes and one asynchronous streaming standby:

```sh
kubectl --kubeconfig="$HOME/.kube/config-prod" -n app-prod get pods -l cnpg.io/cluster=liora-db -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" exec "$primary" -c postgres -- psql -U postgres -d app -c 'SELECT application_name, state, sync_state FROM pg_stat_replication; SHOW synchronous_standby_names;'
```

- [ ] Complete HTTPS, login and disposable item create/read/update/delete using runbook 13.
- [ ] Log in to Adminer with server `db`, database `app` and administrative credentials.

**Done when:** All requested instances are Ready, database identities and schema match, application login/CRUD succeeds, and PROD replication is asynchronous across different nodes.

## Database maintenance

- [ ] Record the current image pair, Argo policies and Jenkins job/trigger settings before work.
- [ ] Block new conflicting deployments and allow active CI/publisher work to finish.
- [ ] Pause root reconciliation before application children; use reviewed declarative maintenance settings.
- [ ] Wait for the database/operator rollout to finish.
- [ ] For backend images requiring connection-pool refresh, change the backend rollout annotation declaratively while retaining its image digest; wait for rollout completion.
- [ ] Require actual login and CRUD after the restart. Readiness probes alone do not check authenticated database use.
- [ ] Restore child policies before root policies and restore the recorded Jenkins settings.

**Stop:** On failed database, replication, login or CRUD checks, keep conflicting deployment activity held and retain diagnostics. Do not reset databases or delete PVCs to clear readiness errors.

## Related procedures

- [Backup installation and isolated PITR](19-cnpg-r2-backup-pitr.md)
- [Storage and replication alert response](../docs/operations/STORAGE_REPLICATION_ALERTS.md)
- [Disaster recovery](../01-Disaster_recovery.md)
