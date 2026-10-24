# Historical procedure record — 18-cloudnative-pg

Archived on 2026-10-24 before the operational-manual rewrite. This preserves
one-time decisions, commands, observations and original limitations. Statements
about current status describe their original checkpoint. Do not use this record
as the installation or incident-response entrypoint. Operator scripts remain
in their original locations.

Current procedure: [18-cloudnative-pg.md](../../runbooks/18-cloudnative-pg.md).

---

# Install fresh CloudNativePG application databases

Use this procedure only with explicit authorization to discard application data.
It is not a logical migration or a database restoration procedure. Work in the
original infrastructure checkout. Complete DEV, then STAGE, then PROD; stop
advancing if an environment fails. Do not rebuild application images or run a
Jenkins regression solely for this replacement.

## Configuration and prerequisites

Install the [pinned operator](../../kubernetes/platform/cloudnative-pg/kustomization.yaml)
independently in each cluster. See its [provenance and compatibility](../../kubernetes/platform/cloudnative-pg/UPSTREAM.md).

| Environment | Namespace | Instances | Volume per instance | Requested / limited CPU | Requested / limited memory |
| --- | --- | --- | --- | --- | --- |
| DEV | app-dev | 1 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |
| STAGE | app-stage | 1 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |
| PROD | app-prod | 2 | 2 GiB local-path | 250m / 1 | 512 MiB / 1 GiB |

PROD requires different node hostnames for its primary and standby. Streaming
replication is asynchronous; no synchronous replication is configured. Four
instances total request 1 CPU, 2 GiB memory and 8 GiB disk. Each operator requests
100m CPU/128 MiB and is limited to 500m CPU/256 MiB. This is a small lab budget,
not a capacity benchmark. Local-path claim sizes are planning requests, not
filesystem quotas; monitor the underlying node filesystem too. WAL and data
share the per-instance volume. Replication slots can retain WAL during standby
trouble; monitor free space and expand before exhaustion. A second replica is
not an off-host backup. `enablePDB: false` keeps operator-generated disruption
budgets outside this checkpoint, as requested; no HPA/PDB rollout is included.

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

Standalone script: [Bootstrap CNPG Secrets](../../scripts/kubernetes/bootstrap-cnpg-secrets.py).

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

The shared application base contains no database workload. Current overlays
select `components/cloudnative-pg`. The independent legacy component used during
the cutover is retained in Git history at `2ff6364` and was removed after all
three environments passed. For a fresh installation, provision the operator
and credentials, then sync the CNPG overlay; skip legacy maintenance and
retirement. The numbered sequence below records conversion of an existing
legacy environment, not instructions to recreate the obsolete workload.

1. Provision bootstrap Secrets and apply the pinned component `cluster.yaml`
   in the selected namespace alongside the legacy database using field manager
   `liora-cnpg-bootstrap`. For PROD render a reviewed local copy with
   `instances: 2`. This creates only the new database; the environment Argo
   Application adopts the same Cluster during step 3. Wait for all instances
   and bound PVCs before switching the application endpoint.
2. Commit zero backend/frontend replicas for that environment and explicitly
   sync that revision. Wait until its application Pods have terminated. Do not
   change routing, namespace, Adminer or database credentials.
3. Select only the CNPG component; restore the original backend/frontend replica
   counts. Its Service patch retains the existing `db` ClusterIP and changes
   only its selector to `cnpg.io/cluster: liora-db`, `role: primary`. Its backend
   ConfigMap changes only the database username to `app_owner`. The backend
   restart after maintenance reloads the new connection configuration. Render and inspect before
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

### Browser CRUD with disposable-item cleanup

Use the environment selection from runbook 13 and its prepared local browser
tools. The existing checker verifies health, browser login, create, read, update,
reload/persistence and optional deletion with both a 404 and UI absence check.
Select the matching public hostname and the existing private HAProxy route;
Chromium retains hostname/SNI and verifies trusted HTTPS.

```sh
acceptance_url="https://$hostname" acceptance_address=192.168.77.240 acceptance_cleanup=true bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
```

Standalone script: [Verify application UI](../../scripts/kubernetes/verify-application-ui.py).
Keep `environment`, `namespace`, `recovery_dir` and `render_dir` exported as in
runbook 13. This operator-invoked check does not create an automatic STAGE
acceptance receipt or satisfy the PROD image-promotion gate. Testing through the
private edge does not independently establish public-origin reachability.

### Database restart and application connection pools

Pin both the controller image and `OPERATOR_IMAGE_NAME` before provisioning
instances. Changing the injected bootstrap image can cause CNPG to refresh
existing Pods; allow its managed shutdown/startup to finish, then recheck every
instance. A readiness snapshot during a managed refresh is not a completed gate.

The existing application image has long-lived SQLAlchemy connections without
pool pre-ping. After a database restart, an old pooled connection can make the
first login fail. For this installation the final committed backend database
revision annotation rolls the existing images after the last operator refresh;
DEV's overlay explicitly retains that annotation. Wait for those backend
rollouts, then repeat login/CRUD before restoring deployment automation. Keep
future operator/database restarts coordinated with application reconnects until
a separately reviewed application change provides automatic stale-pool handling.
Do not rebuild application images as part of this procedure.

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

## R2 physical backup and restoration

The fresh-installation checkpoint did not configure backups. Phase 10.2 has
subsequently added physical base backups, continuous WAL and isolated PITR.
Use [runbook 19](../../runbooks/19-cnpg-r2-backup-pitr.md) for current operations and
[the Phase 10.2 report](PHASE10_2_REPORT.md) for scope,
measured objectives and limitations. Never treat a raw copy of a running PVC
as a database backup.
