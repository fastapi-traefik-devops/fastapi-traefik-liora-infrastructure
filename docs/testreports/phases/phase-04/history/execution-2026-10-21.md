# Phase 4 report — STAGE deployment and DEV/STAGE isolation

Status on 2026-10-21: **complete**. Phase 5 has not started.

## Source and scope

The operator authorized the next phase after the recovery validator work.
This phase deployed STAGE only, following the database-first procedure in
[runbook 13](../../../../../runbooks/13-deploy-application-manifests.md).

- Worktree: `/home/root-admin/liora-infrastructure-migration`.
- Branch: `migration/liora-phase0`; applied revision
  `1e39a5b6bfd1479160143cd6c8d7338c2fd4954e`.
- Imported application deployment source:
  `b98a22e48527c256193ed65c10307eb574b27ab6`.
- Read-only application checkout: verified origin
  `git@github.com:fastapi-traefik-devops/fastapi-traefik-liora-application.git`,
  clean HEAD `1a5b24f096dd1a6234fa101f8648e40db88b52c7`.
- Target: `app-stage`, explicit kubeconfig
  `/home/root-admin/.kube/config-dev-stage`, API
  `https://192.168.77.11:6443`, nodes `k3s-1-01`–`03` (VMs 201–203).

No application manifests or credentials required changes. The application
repository and kind reference cluster were not modified. No merge or push was
performed. PROD retains prepared Secrets and no application workloads.

## Deployment and readiness

The complete recovery validator passed offline with strict warnings enabled:
zero errors, zero warnings, exit 0. STAGE's live backend/database Secrets were
compared with recovery in memory and matched; no values were printed.

The STAGE overlay rendered 13 objects, split into 3 configuration/storage,
2 database, 1 prestart and 7 application objects. Deployment proceeded through
these gates:

1. Apply ConfigMaps, PVC, database Service and PostgreSQL Deployment.
2. Wait for PVC Bound and PostgreSQL Ready; `pg_isready` accepted connections.
3. Apply prestart and wait for Complete before applying remaining workloads.
4. Wait for backend, frontend and Adminer Ready; verify private acceptance.

All four Deployments have one Ready/Available replica. All workload containers
have zero restarts. Prestart completed once, from `16:06:39Z` to `16:07:49Z`.
The database reports Alembic revision `1a31ce608336`.

STAGE's `postgres-vol` is a Bound 1Gi RWO claim using `local-path`, PV
`pvc-0f77a2ff-c120-4c10-9e79-0a1e39fca976`, on `k3s-1-03`. DEV retains its
distinct PV `pvc-b28aa15c-c4ec-4f8b-9459-f1d2c28bb1a9` on `k3s-1-02`.
Both application volumes and their data were retained.

The selected application tag remains
`sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`. Actual container image IDs match
the rendered pins:

| Container | Node | Actual image ID |
| --- | --- | --- |
| backend | k3s-1-02 | `ghcr.io/fastapi-traefik-devops/fastapi-backend@sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` |
| prestart | k3s-1-02 | `ghcr.io/fastapi-traefik-devops/fastapi-backend@sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` |
| frontend | k3s-1-01 | `ghcr.io/fastapi-traefik-devops/fastapi-frontend@sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |
| postgres | k3s-1-03 | `docker.io/library/postgres@sha256:557fea37a744d5f4c8faab304b0a90858b53ab119735a88c131fd19dab802f36` |
| adminer | k3s-1-02 | `docker.io/library/adminer@sha256:34d37131366c5aa84e1693dbed48593ed6f95fb450b576c1a7a59d3a9c9e8802` |

Initial PostgreSQL readiness probes reported initialization, then recovered.
An early HTTP request before backend readiness returned 503; acceptance ran
after the rollout gates and passed. No deployment retry or resource deletion
was needed.

## Private browser and isolation evidence

A localhost-only Traefik Service forward exposed HTTP on port 18080. The
existing browser acceptance script resolved `stage.liora.aprt.info` to loopback
inside Chromium, using `http://stage.liora.aprt.info:18080` without changing
system hosts or DNS. It verified:

- Backend health HTTP 200 with `true`, frontend and login page HTTP 200.
- Actual UI authentication as `admin007@liora.aprt.info` using STAGE recovery.
- UI item creation, editing, visibility after reload and authenticated API read.

The retained STAGE marker is ID `319fb130-87ec-4de9-8ce9-e895b2f65710`, title
`acceptance-stage-37547300d732-updated`. DEV's retained marker remains ID
`772a3eed-dcb0-409d-be65-bf58354c8d70`, title
`acceptance-dev-1f43ffe0d91a-updated`.

Both environments authenticated independently, passed health and returned their
own marker/title with HTTP 200. Each returned HTTP 404 for the other marker.
Read-only SQL in each namespace's PostgreSQL confirmed exactly one own marker
row and zero foreign marker rows. Each rejected the other's signed token with
HTTP 403, the status used by the application's invalid-token handler. The first
extra token check expected 401; its assertion was corrected after inspecting
the read-only source, and the full isolation check then passed. No application
change was needed.

Local evidence under `/home/root-admin/liora-render/`:

- `stage/acceptance.json`: browser result and marker metadata.
- `stage/isolation.json`: mutual health/API/SQL/token results.
- `{dev,stage}/phase4-workloads.json`: workload, image ID, volume and node records.
- `stage/check-isolation.py`: local read-only API/SQL check, reading credentials
  at runtime without embedding or logging them.

No passwords, access tokens, browser state or traces were saved in evidence.
The temporary port-forward was stopped. Keep both markers through Phase 5 for
PROD isolation testing; remove only the synthetic acceptance items after all
three environments pass. The runbook now explains this retention order.

## Files changed and remaining boundaries

This documentation-only repository increment updates `README.md`,
`docs/ARCHITECTURE.md`, `docs/testreports/IMPLEMENTATION_PLAN.md`,
`docs/testreports/archive/migration-procedures/application-source-history.md`, and
`runbooks/13-deploy-application-manifests.md`, and adds this report. The changes
record verified STAGE status and the marker retention needed for Phase 5.

All Phase 4 checklist items passed: independent STAGE deployment, readiness,
private browser persistence and mutual DEV/STAGE isolation. DEV kept its
existing Pods, image pins, Ready replicas and zero restarts. All six nodes were
Ready at final verification. PROD has no Deployments, Pods, PVCs or Jobs.

Public DNS/routing, trusted TLS, canonical HTTPS origins, data restoration,
backup recovery and node failure behavior remain unverified. STAGE retains its
configured HTTPS origin and `app-tls` reference; no TLS Secret was created, and
private HTTP acceptance does not establish trusted HTTPS.

The next phase, after operator confirmation, is PROD deployment on VMs 211–213
with the already approved image pair, two backend/frontend replicas, private
acceptance and checks against both nonprod markers. Stop here before Phase 5.
