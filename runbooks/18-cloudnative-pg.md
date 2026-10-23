# Install fresh CloudNativePG application databases

Use this procedure only with explicit authorization to discard application data.
It is not a logical migration or a database restoration procedure. Work in the
original infrastructure checkout. Complete DEV, then STAGE, then PROD; stop
advancing if an environment fails. Do not rebuild application images or run a
Jenkins regression solely for this replacement.

## Configuration and prerequisites

Install the [pinned operator](../kubernetes/platform/cloudnative-pg/kustomization.yaml)
independently in each cluster. See its [provenance and compatibility](../kubernetes/platform/cloudnative-pg/UPSTREAM.md).

| Environment | Namespace | Instances | Volume per instance | Requested / limited CPU | Requested / limited memory |
| --- | --- | --- | --- | --- | --- |
| DEV | app-dev | 1 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |
| STAGE | app-stage | 1 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |
| PROD | app-prod | 2 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |

PROD requires different node hostnames for its primary and standby. Streaming
replication is asynchronous; no synchronous replication is configured. Four
instances total request 1 CPU, 2 GiB memory and 8 GiB disk. Each operator requests
100m CPU/128 MiB and is limited to 500m CPU/256 MiB. This is a small lab budget,
not a capacity benchmark. WAL and data share the per-instance volume. Replication
slots can retain WAL during standby trouble; monitor free space and expand before
exhaustion. A second replica is not an off-host backup.

Record actual server versions, extensions, image digests, Secrets references,
PVC/PV bindings, free capacity, Argo ownership and approved Jenkins states before
changes. Preserve private evidence under `.local-work/private/phase10/`, mode
0700 directories/0600 files. Do not print passwords or authentication tokens.

## Hold conflicting automation

Disable only new main CI scheduling and remove its polling trigger; allow
in-flight CI and its trusted publisher to finish. Once queue and running work
are empty, disable the trusted publisher. Do not abort retained work or enable
unrelated jobs. Save the previous job settings for exact restoration.

Pause root Argo automation before pausing its application children, so root
self-healing cannot undo the hold. Record their original automation policies.
Use committed maintenance replica counts and explicit revision-bound Argo syncs;
do not use imperative scaling that self-healing can reverse. Keep application
image entries untouched. Argo roots remain held until all environments pass.

## Install operators and bootstrap credentials

For NONPROD use `$HOME/.kube/config-dev-stage`; for PROD use
`$HOME/.kube/config-prod`. Inspect the server address before each operation.

```sh
kubectl --kubeconfig="$kubeconfig" apply --server-side --field-manager=liora-cnpg-platform -k kubernetes/platform/cloudnative-pg
kubectl --kubeconfig="$kubeconfig" -n cnpg-system rollout status deployment/cnpg-controller-manager --timeout=600s
kubectl --kubeconfig="$kubeconfig" apply -f "kubernetes/gitops/argocd/$argocd_cluster/settings.yaml"
```

The operator owns its platform installation. Argo's `fastapi` AppProject permits
only namespaced CNPG Cluster objects in its own application namespaces. Its
Cluster health customization waits for Ready=True and every requested instance
before allowing the later prestart Sync wave. The operator's generated Pods,
Services, certificates and PVCs belong to the environment Cluster.

Create bootstrap Secrets from existing application credentials:

```sh
bash scripts/local-python.sh scripts/kubernetes/bootstrap-cnpg-secrets.py --kubeconfig "$kubeconfig" --environment "$environment"
```

Standalone script: [Bootstrap CNPG Secrets](../scripts/kubernetes/bootstrap-cnpg-secrets.py).

It keeps existing backend/db passwords unchanged, creates `cnpg-app` with
username `app_owner` and `cnpg-superuser` with username `postgres`, and refuses
to overwrite mismatching existing CNPG credentials. These private Kubernetes
Secrets are not Git resources. Their values can be regenerated from the
existing environment recovery inputs; no new recovery password is introduced.

The `app` database belongs to `app_owner`. CNPG initdb installs `uuid-ossp` before
the existing Alembic process runs. The application uses the non-superuser owner;
`postgres` remains available with the existing database password for Adminer
administration. Keep the existing application initial administrator credentials,
signing key, registry credentials and all other Secrets unchanged.

## Transition one environment

The shared application base contains no database workload. Each overlay opts
into `components/legacy-postgres` or `components/cloudnative-pg`, allowing the
other environments to remain unchanged during the transition.

1. Add the CNPG Cluster beside the legacy workload in the selected environment
   and provision its Secrets. For PROD set `instances: 2`. Sync the exact reviewed
   commit and wait for all CNPG instances, bound PVCs and correct ownership.
2. Commit zero backend/frontend replicas for that environment and explicitly
   sync that revision. Wait until its application Pods have terminated. Do not
   change routing, namespace, Adminer or database credentials.
3. Select only the CNPG component; restore the original backend/frontend replica
   counts. Its Service patch retains the existing `db` ClusterIP and changes
   only its selector to `cnpg.io/cluster: liora-db`, `role: primary`. Its backend
   ConfigMap changes only the database username to `app_owner`. The backend
   template annotation causes clients to reconnect. Render and inspect before
   publishing, then explicitly sync the exact revision with hooks enabled.
4. CNPG readiness is wave -2; existing `prestart` runs at Sync wave 0 using the
   unchanged backend image. It waits for SQL connectivity, runs Alembic to head
   and initializes the existing administrator. Backend/frontend wave 1 then
   resume writes after these basic gates; no extended observation window.
5. Check database/owner/extensions, migration head, image references and actual
   running IDs, frontend/backend readiness, HTTPS, existing administrator login,
   and disposable item create/read/update/delete. Check Adminer's existing
   private endpoint and database connectivity. For PROD also check different
   nodes, `pg_stat_replication` streaming/async and standby recovery/replay.
6. Only after checks pass, remove the obsolete `postgres-deployment`, `db-config`
   and **only** the selected environment's old `postgres-vol` PVC. The PVC has
   prune/delete protection, so retire it explicitly after checking its saved
   UID/PV and verifying no Pod uses it. Confirm its old PV deletion and the CNPG
   PVCs remain Bound. Never delete namespaces or use wildcard PVC deletion.
7. Reconcile Argo again and require Synced/Healthy, correct resource ownership
   and no pending unexpected pruning before proceeding to the next environment.

Fresh databases intentionally do not retain old accounts, rows or synthetic
acceptance markers. Existing initialization credentials recreate application
access. Old image rollback does not restore discarded data or undo migrations.
If a step fails, keep deployment/promotion held, stop before the next environment
and retain private diagnostics; do not invent a data-preserving rollback claim.

## Restore automation and record boundaries

Restore each child's original policy, then its root's original policy. Verify
both roots and all children reconcile the published revision. Restore only the
previously approved main polling trigger (approximately every two minutes) and
trusted publisher enablement after checking the queue and running work. Leave
unrelated jobs, schedules and indexing disabled. Preserve administrator/user
hashes, Jenkins build history and unrelated PVC/Secret identities.

Record fresh installation and existing-image application results separately
from CI/CD regression: the latter is not rerun here. PROD application promotion
remains blocked by its pending automatic STAGE acceptance gate. Phase 9 startup,
observer, acceptance serialization and promotion work remain separate tasks.

## Next database task: R2 physical backup and restoration

Integrate the supported Barman Cloud Plugin with environment-specific identities
and object-store destinations: PostgreSQL physical base backups plus continuous
WAL archiving to R2. Configure credentials, schedules, retention and capacity,
then perform an **isolated restoration exercise** with explicit recovery-point
checks. Never treat a periodic raw copy of a running PVC as a database backup.
No R2 resources, WAL archiving, schedules or retention are configured by this
installation. Do not claim backup, PITR or recovery readiness before that task.
