# Phase 10 — Fresh CloudNativePG installation

Status: **in progress**. Authorized scope is fresh DEV/STAGE/PROD application
databases, disposable old application data, unchanged frontend/backend image
pairs. No dump/restore. The Phase 9 Jenkins backlog remains separate.

## Preflight and selection

Both original checkouts were clean at entry; existing commits and private
operator inputs are retained. PostgreSQL 16.6 actually runs in all environments;
`app` includes `plpgsql` and `uuid-ossp`. Current database storage is one 1 GiB
local-path PVC per namespace. Jenkins has zero running/queued work; only main
and trusted publisher are enabled. Private baselines capture credentials hashes,
PVC identities, deployment images, Argo settings and Jenkins state.

Selected CNPG 1.30.1 and PostgreSQL 16.15-system-trixie, each digest-pinned.
K3s 1.36.5 is within CNPG's supported Kubernetes matrix. Barman Cloud Plugin
requirements permit this operator version; the plugin is not installed.

Four instances total: DEV 1, STAGE 1, PROD 2 with required hostname anti-affinity
and asynchronous streaming. Each requests 250m CPU/512 MiB, limits 1 CPU/1 GiB,
and claims 2 GiB local-path. Each cluster's operator requests 100m/128 MiB and
limits 500m/256 MiB. `app_owner` owns `app`; existing passwords and initial
application administrator settings are reused. `postgres` remains an admin role.

## Execution and acceptance

Pending live installation and environment cutovers. Follow
[runbook 18](../../runbooks/18-cloudnative-pg.md). Do not interpret prepared
manifests or local tests as application acceptance.

## Explicit remaining boundaries

Full Jenkins CI/CD regression is not rerun solely for this database change.
Application images are neither rebuilt nor published. Vulnerability work is
deferred. PROD application promotion stays blocked by the pending automatic
STAGE acceptance gate. No failover or host-reboot exercise is included.

R2 base backups, WAL archiving, retention and an isolated restoration exercise
are the next database task. No backup/recovery readiness is claimed.
