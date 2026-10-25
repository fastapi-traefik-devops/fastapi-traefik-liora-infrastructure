# Phase 3 report — DEV deployment and private acceptance

Status on 2026-10-21: **complete**. Phase 4 has not started.

## Source, repository and documentation location

- Application deployment source: upstream
  `b98a22e48527c256193ed65c10307eb574b27ab6`.
- Application checkout remains read-only at
  `1a5b24f096dd1a6234fa101f8648e40db88b52c7`.
- Applied manifest revision: `e144202a0cbd77e0b6a803c4952967a706590ff8`.
- Branch/worktree: `migration/liora-phase0` in
  `/home/root-admin/liora-infrastructure-migration`.
- No merge into the original infrastructure branch or push was performed.

At the operator's request, all seven Markdown files from the Kubernetes tree
were moved with Git renames into `docs/testreports/`, including the nested
migration provenance document. Links and path references were updated, and the
plan/instructions now direct future plans and reports here. The moves are in
commit `e144202`. Deployment YAML and source-history TSV paths are unchanged.

## Deployment sequence and live result

Every DEV deployment operation used the explicit
`/home/root-admin/.kube/config-dev-stage` kubeconfig, whose API server and exact
node names were checked before applying resources. The target is `app-dev` on
VMs 201–203, API `https://192.168.77.11:6443`.

The DEV overlay rendered 13 objects. The existing standalone splitter produced
3 configuration/storage, 2 database, 1 prestart and 7 application objects.
Application was deliberately staged:

1. Apply both ConfigMaps and the application PVC, then the database Service and
   PostgreSQL Deployment.
2. Wait for `postgres-vol` Bound, database Deployment Ready and successful
   `pg_isready` before creating prestart.
3. Complete prestart, including schema migrations and initial account creation,
   after the credential compatibility correction described below.
4. Apply backend, frontend, Adminer, remaining Services and DEV Ingress only
   after prestart succeeds; wait for all four Deployments Ready.
5. Check private ingress health, actual UI authentication and persisted data.

The 1Gi RWO application claim `postgres-vol` is Bound to
`pvc-b28aa15c-c4ec-4f8b-9459-f1d2c28bb1a9` through `local-path` on
`k3s-1-02`. Unlike the Phase 2 probe claims, this is the application database
volume and was retained. The live Alembic revision is `1a31ce608336`.

PostgreSQL, backend, frontend and Adminer each have one Ready/Available replica.
The successful prestart Job has one completion. All workload Pods run on the
expected k3s-1 nodes, with zero restarts at final verification. Image references
remain the Phase 1 DEV pins:

- Backend and prestart: `sha-3303e93b753e8282dc7b461c583fb8ace43574a1`, digest
  `sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b`.
- Frontend: the same tag, digest
  `sha256:a8d07b6be8ae8c76cc8133c885ba8ec3c095ded005db251aaf6a190e88426f82`.
- PostgreSQL `postgres:16.6` and Adminer `adminer:4.8.1` remain in place.

Actual container image IDs were recorded from Kubernetes:

| Container | Node | Pod phase | Actual image ID |
| --- | --- | --- | --- |
| adminer | k3s-1-03 | Running | `docker.io/library/adminer@sha256:34d37131366c5aa84e1693dbed48593ed6f95fb450b576c1a7a59d3a9c9e8802` |
| backend | k3s-1-03 | Running | `ghcr.io/fastapi-traefik-devops/fastapi-backend@sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b` |
| frontend | k3s-1-03 | Running | `ghcr.io/fastapi-traefik-devops/fastapi-frontend@sha256:a8d07b6be8ae8c76cc8133c885ba8ec3c095ded005db251aaf6a190e88426f82` |
| postgres | k3s-1-02 | Running | `docker.io/library/postgres@sha256:557fea37a744d5f4c8faab304b0a90858b53ab119735a88c131fd19dab802f36` |
| prestart | k3s-1-03 | Succeeded | `ghcr.io/fastapi-traefik-devops/fastapi-backend@sha256:ea2d0aaf163f15f1bf749ee69822ebe33e619d2a00a5813d348732936b56f00b` |

## Administrator password compatibility correction

The first prestart run reached the database and applied migrations, then failed
creating the initial account: the generated administrator password had 43
characters, while the application's UserCreate password field allows 8–40.
This was an error in the initial credential preparation, not an image or
PostgreSQL failure. Failure output was inspected with credential redaction.

Only `FIRST_SUPERUSER_PASSWORD` was regenerated, using independent 32-character
random values for DEV, STAGE and PROD. The ignored original checkout's
`recovery/recovery.yaml` and corresponding live `backend-secrets` fields were
updated and compared in memory. Existing signing keys, database passwords,
GHCR credentials and controller recovery material were preserved. This corrected
STAGE/PROD's prepared credentials without deploying their application workloads.
No credential value was committed or saved in acceptance output.

After reviewing that this was a fresh database with failed initial account
creation, the failed DEV Job and its Pods were removed and prestart recreated.
Its migrations were safely rerun to the same schema revision, initial account
creation succeeded, and the Job reached Complete. The database PVC was not
recreated or deleted.

Commit `fef05c8` adds the application password-length guard to both bootstrap
script forms and documents the limit. A synthetic overlong-password fixture
was rejected before any cluster command; standalone and inline versions remain
identical. Presence checks alone had been insufficient in Phase 2.

## Private acceptance evidence

The check used an explicitly qualified, localhost-only Traefik Service forward
on port 18080. CLI requests supplied the DEV Host header. A headless Chromium
check resolved `dev.liora.aprt.info` to loopback inside the browser and used
`http://dev.liora.aprt.info:18080`; no system hosts file, DNS, TLS, ingress edge
address or public routing was changed.

Verified results:

- Backend `/api/v1/utils/health-check/`: HTTP 200 and `true` through Traefik.
- Frontend `/` and login page: HTTP 200.
- Browser login as `admin007@liora.aprt.info`: token endpoint HTTP 200 and the
  authenticated welcome screen visible.
- Item creation and editing through the actual UI: successful API responses
  and updated item visible in the table.
- Browser reload: updated item remains visible; authenticated API read returns
  HTTP 200 with the expected title.
- Direct read-only SQL against the K3s DEV PostgreSQL database confirms exactly
  one matching marker row, establishing the database used by the UI check.

The synthetic isolation marker was intentionally retained:

- ID: `772a3eed-dcb0-409d-be65-bf58354c8d70`.
- Title: `acceptance-dev-1f43ffe0d91a-updated`.
- Operator record: `/home/root-admin/liora-render/dev/acceptance.json`.

Use this marker during Phase 4's DEV/STAGE isolation check. It contains no real
personal data. The temporary ingress forward was stopped after acceptance;
application resources and the marker remain. The record contains only result,
environment, URL and marker metadata, with no password or access token. Browser
authentication state and traces were not saved.

Commit `d419a0c` adds the reusable browser acceptance script and links it directly
under its invocation block in the runbook. The execution used Playwright 1.64.0,
PyYAML 6.0.3 and Chromium build 1248. Required browser libraries were extracted
into `/home/root-admin/liora-browser-deps` and supplied through `LD_LIBRARY_PATH`;
no privileged system-package installation was performed. This tooling is local,
not an application dependency or application-repository modification.

## Scope checks and limitations

All six K3s nodes were Ready at final verification. STAGE and PROD retain their
namespaces and required Secrets, but have no application Pods, PVCs, Jobs or
Deployments. The existing kind reference cluster was not changed. DEV image
pins, replicas, application manifest structure and source history are unchanged.

Phase 3 establishes DEV through the temporary private HTTP origin. It does not
verify public DNS/routing, canonical-origin CORS at standard ports, trusted TLS,
backup restore, node failover, data replication or the later environments.
Administrative ingress was not added for Adminer. No Phase 3 blockers remain.

## Exact repository files changed in this increment

The seven renamed documents now reside at:

```text
docs/testreports/evidence/records/application-repository-cleanup.md
docs/testreports/IMPLEMENTATION_PLAN.md
docs/testreports/archive/migration-procedures/application-source-history.md
docs/testreports/phases/phase-00/history/execution-2026-10-21.md
docs/testreports/phases/phase-01/history/execution-2026-10-21.md
docs/testreports/phases/phase-02/history/execution-2026-10-21.md
docs/testreports/archive/prompts/initial-migration.md
```

| Other change | Purpose |
| --- | --- |
| README.md | New report location and current DEV/STAGE/PROD status |
| docs/ARCHITECTURE.md | Record actual DEV deployment and private acceptance boundary |
| docs/testreports/IMPLEMENTATION_PLAN.md | Mark Phase 3 checks complete; retain later phase gates |
| docs/testreports/archive/migration-procedures/application-source-history.md | Link source provenance to separate live DEV evidence |
| docs/testreports/phases/phase-03/history/execution-2026-10-21.md | This report |
| scripts/kubernetes/bootstrap-application-secrets.py | Enforce the application's administrator password length |
| scripts/kubernetes/verify-application-ui.py | Reusable private health/login/UI item/persistence check |
| runbooks/13-deploy-application-manifests.md | Updated report links, password constraint, browser script alternative and verified status |

Local-only change: administrator password fields in ignored recovery YAML and
the three live backend Secrets, described above. Application YAML was applied
without edits; no live credential, private key or state was added to Git.

## Checklist and next action

- Complete: DEV deployment on its assigned namespace/cluster, with PostgreSQL
  verified before prestart and prestart completed before the application group.
- Complete: PVC Bound, PostgreSQL Ready, prestart Complete and backend,
  frontend and Adminer Ready; applied digests and actual image IDs recorded.
- Complete: private health, UI login and database write/read/update verification.
- Deferred: Phase 4 STAGE deployment and mutual DEV/STAGE isolation checks.

Next small action after confirmation: deploy STAGE only with its own PVC and
corrected credentials, repeat readiness and UI acceptance, verify both marker
isolation directions, and confirm DEV remains healthy. Stop after the Phase 4
report before proceeding to PROD.

## Historical procedure archive

The 2026-10-24 manual rewrite preserves the previous procedural text separately:

- [Phase3 5 Application Procedures Archive](../../../archive/migration-procedures/phase3-5-application-procedures-archive.md)

Current operator entrypoint: [procedure index](../../../../../runbooks/README.md).
