# Phase 10 — Fresh CloudNativePG installation

Date: 2026-10-23. **10.1 complete: fresh database installation and existing-image
application checks passed in DEV, STAGE and PROD.** Approved Argo and Jenkins
automation is restored. This is not full Phase 10 completion: R2 backup and
isolated restoration remain pending. Separately delegated Phase 9 Jenkins
work remains open; PROD image promotion remains blocked.

## Scope and preflight

Worked in both original checkouts. Infrastructure started clean at `940b90f`;
application stayed unchanged at `3459d5a`. Existing commits, imported history,
private recovery inputs, keys and state were preserved. No repository copy,
force-push, history rewrite, namespace deletion or application image rebuild.
Reviewed infrastructure commits were pushed only after explicit owner approval.

All three old databases actually ran PostgreSQL 16.6, database `app`, with
`plpgsql` and `uuid-ossp`; each used one 1 GiB local-path PVC and the application
connected as `postgres`. Existing application data was explicitly disposable.
There was **no dump/restore, logical migration or old-data transfer**.

Private baselines recorded deployment images, PVC identities, Secret hashes,
Argo policies and Jenkins user/job/build state. Jenkins had zero queued/running
work; only main and trusted publisher were enabled. New main work/polling was
held, then the idle publisher. Roots were paused before children so self-healing
could not undo maintenance. Each environment's zero backend/frontend replica
state and cutover were committed and explicitly synced at an exact revision.

## Versions and resource configuration

The [operator provenance](../../../../../kubernetes/platform/cloudnative-pg/UPSTREAM.md)
records official release sources, compatibility and hashes. Both clusters run
the pinned CNPG 1.30.1 operator, compatible with the actual K3s 1.36.5. Operand:
PostgreSQL **16.15-system-trixie**, preserving major 16 and selecting its current
suitable stable minor. Controller and injected bootstrap images use the same
OCI digest; PostgreSQL is also digest-pinned.

- Operator: `ghcr.io/cloudnative-pg/cloudnative-pg:1.30.1@sha256:923c267ec29636db3bee20f993d0ec4973fa22998e1adad37da79e4d32b5bc07`.
- PostgreSQL: `ghcr.io/cloudnative-pg/postgresql:16.15-system-trixie@sha256:8ca5699981c25db72e549e9fa69561bac233df15b9b1e3a6282847b0629bb5ea`.
- Each database instance requests 250m CPU/512 MiB, limits 1 CPU/1 GiB,
  and claims 2 GiB local-path. Four instances request 1 CPU, 2 GiB RAM and
  8 GiB PVC capacity total. Local-path requests are not filesystem quotas.
- Each operator requests 100m CPU/128 MiB and limits 500m CPU/256 MiB.
  Node metrics showed sufficient headroom; no load/capacity benchmark is claimed.
- PROD has required hostname anti-affinity. Streaming is asynchronous;
  `synchronous_standby_names` is empty and no synchronous replication is configured.
- `enablePDB: false` removes CNPG's default generated disruption budgets from
  this checkpoint. No application HPA/PDB work was introduced.

## Environment results

Each namespace owns a distinct `liora-db` Cluster and its instance PVCs.
`db` retains its original ClusterIP and selects only the CNPG primary.

| Environment | Ready instances | Database placement | Stable application endpoint | Initialization / application checks |
| --- | --- | --- | --- | --- |
| DEV | 1 | liora-db-1: k3s-1-02 | 10.43.207.153:5432 | Passed |
| STAGE | 1 | liora-db-1: k3s-1-02 | 10.43.181.161:5432 | Passed |
| PROD | 2 | liora-db-1: k3s-2-02, liora-db-2: k3s-2-03 | 10.43.7.140:5432 | Passed |

`app_owner` owns database `app`, `alembic_version`, `user` and `item`, and is
not a superuser. CNPG bootstrap installed `uuid-ossp`; existing prestart/Alembic
completed successfully at **`1a31ce608336`** in all environments. Argo's Cluster
health waits for Ready=True and all requested instances at wave -2 before the
existing Sync-wave-0 initialization hook and later application workloads.

Current backend/frontend replicas are DEV 1/1, STAGE 1/1, PROD 2/2. Ready Pods'
actual image IDs match the original digest pair in every environment:

| Environment | Existing application revision | Backend digest | Frontend digest |
| --- | --- | --- | --- |
| DEV | `3303e93b753e8282dc7b461c583fb8ace43574a1` | `sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b` | `sha256:a8d07b6be8ae8c76cc8133c885ba8ec3c095ded005db251aaf6a190e88426f82` |
| STAGE | `3459d5a4f1d39473fd845674dfc7f591bee81059` | `sha256:cc32c4e72a58a5b1b579e1909d9c31c455ebee3cba0a431bd957ecf51e9c2d0c` | `sha256:87acf879741853a6e3d43c766ad0d93d488adf12b4e89891b9295739d6f6b0b5` |
| PROD | `c375967ac5b3dd7a0a6867758e16b057c733bb2d` | `sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` | `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |

Browser checks passed for backend health, frontend, existing administrator
login, disposable item create/read/update, reload/persistence, deletion and
subsequent 404/UI absence. No synthetic item is retained. HTTPS used the
existing private HAProxy address `192.168.77.240` with the canonical hostname,
SNI and trusted certificate validation. Fresh external public-origin reachability
is not claimed; routing, DNS, NAT and certificates were unchanged.

Native Adminer browser login passed for every environment using `db`, database
`app`, administrative user `postgres` and the existing password. Owner and
administrator password authentication also passed directly through `db`.
No existing Secret values changed. New private `cnpg-app`/`cnpg-superuser` Secrets
are derived from the existing environment password; the recovery YAML schema
and private password inputs do not need changes. The credentials table helper
now reads CNPG administrative credentials instead of the retired `db-config`.

PROD's primary on `k3s-2-02` reports one standby on `k3s-2-03` in
`streaming` / `async`. The standby is in recovery, its WAL receiver is streaming,
and the replayed database has the same Alembic head. No failover or host-reboot
exercise was performed.

## Corrections and retained failed checks

Pinning `OPERATOR_IMAGE_NAME` as well as the controller image caused a managed
instance refresh. An initial PROD pre-cutover SQL check landed during shutdown
and failed; no PROD maintenance sync was started until all databases were ready
again and asynchronous replication was rechecked. DEV/STAGE used CNPG's normal
180-second smart shutdown followed by fast shutdown before replacement Pods
became Ready. This was configuration reconciliation, not a failover test.

A final DEV login then exposed an old SQLAlchemy pooled connection after that
restart (one backend HTTP 500). A repeat succeeded, but automation remained held.
Commit `476b009` rolls unchanged backend images after initialization and retains
the rollout annotation in DEV, whose overlay otherwise replaces annotations.
Final database, digest and browser CRUD checks passed in **all three**
environments after those backend rollouts. Future database/operator restarts
still require coordinated reconnects until a separately reviewed application
change handles stale pools automatically. No application rebuild was made.

Private failed-attempt results and sanitized diagnostics remain alongside the
successful evidence. No failed attempt is relabeled as passing.

## Retirement, ownership and restored automation

Only after each environment passed were its old `postgres-deployment`,
`db-config` and specifically identified `postgres-vol` PVC removed. Saved PVC
UIDs/PV names were checked, old Pods released the claims, and old PV deletion
completed. All four new CNPG PVCs remain Bound. The temporary legacy component
was retired from active Git files; its full history remains available.

The operator installation has its platform field manager; each application Argo
Application owns its namespace-local Cluster. Generated instance/storage/TLS
resources belong to CNPG. AppProjects allow only the namespaced CNPG Cluster
kind in their existing environment destinations. No new cluster-wide rights
were granted to the application projects.

Both roots and all three application Applications are **Synced/Healthy** at
code revision `476b00972c8dd6ac4060a2ef2db1f54f96d1b153`, with their original
sync/prune/self-heal policies restored. Jenkins main and trusted publisher are
enabled; main's sole SCM trigger is **`H/2 * * * *`**. Unrelated jobs, nightly
schedules and recurring indexing remain disabled; controller executors remain
zero, queue/running work empty. The managed multibranch main child rejects XML
configuration writes; its saved enabled state and trigger were restored through
the existing administrative job-control/polling helper without permission changes.

Preservation checks matched all **67** pre-existing Secret UIDs/data hashes,
all **9** unrelated PVC UIDs/PV bindings, Jenkins user configuration hashes,
retained build counts and approved job/trigger states. Existing admin API
authentication works. No new Jenkins build was requested: latest main/publisher
builds remain **#16 / #35**. Pipeline logic, helper pins, trusted separation,
credentials, retained history and the controller startup guard are unchanged.
No credential value appears in tracked changes.

## Validation and evidence

- Five local infrastructure checks passed: independent CNPG rendering with
  unchanged image pairs, primary selector/role/count/placement boundaries,
  preserved rollout marker, CNPG render splitting, credential-table references,
  secret-safe bootstrap/idempotence and controller/bootstrap digest equality.
- Twenty-seven existing application registry/promotion fixture tests passed.
  These are local helper checks, **not** a Jenkins build or CI/CD regression.
- Environment manifests passed server-side dry-run before their cutovers;
  actual Argo hook execution, ownership and reconciliation were checked.
- Operational and browser evidence is retained privately under
  `.local-work/private/phase10/`; directories/files are protected and ignored.
  No private evidence or credential values are committed. Results distinguish manual application
  checks from deferred automatic release acceptance.

Key commits: `2ff6364` isolated legacy resources; `f8f15ea` pinned/provisioned the
platform; DEV `4e02219`, STAGE `a812f38`, PROD `0502dcb` selected CNPG independently;
`241cdf1` retired old manifests; `476b009` finalized backend reconnects.

## Remaining work and acceptance limits

**Full Jenkins CI/CD regression was not rerun.** No application images were
rebuilt or published. Existing DEV/STAGE promotion records were not changed.
Vulnerability scans/remediation remain deferred. No ingress VIP, certificate,
logging, Jenkins-polishing, observer or expanded-promotion work was performed.

**Next database task:** supported Barman Cloud Plugin, separate environment
backup identities/destinations, PostgreSQL physical base backups plus continuous
WAL archiving to R2, explicit schedules/retention/capacity, and an **isolated
restoration exercise**. R2 database-backup buckets/credentials, backup
schedules, WAL archiving and retention are not configured. Replication is not backup, and no backup,
PITR or recovery readiness is claimed.

**Separately delegated Phase 9 work remains pending:** controller restart guard
cutover, automatic STAGE observer/acceptance receipts and serialization, manual
DEV/PROD promotion and rollback. PROD application promotion stays explicitly
blocked until the agreed automatic acceptance gate is implemented and verified.
The database checks neither satisfy nor bypass that gate.

Procedure: [runbook 18](../../../../../runbooks/18-cloudnative-pg.md). Current execution
order: [implementation plan](../../../IMPLEMENTATION_PLAN.md).

Subsequent backup work: [Phase 10.2](r2-backup-pitr-2026-10-23.md) records implemented
physical backups/WAL and isolated PITR. Earlier R2-pending statements in this
report describe the completed fresh-installation checkpoint.

## Historical procedure archive

The 2026-10-24 manual rewrite preserves the previous procedural text separately:

- [Phase10 Database Transition Archive](../../../archive/migration-procedures/phase10-database-transition-archive.md)

Current operator entrypoint: [procedure index](../../../../../runbooks/README.md).
