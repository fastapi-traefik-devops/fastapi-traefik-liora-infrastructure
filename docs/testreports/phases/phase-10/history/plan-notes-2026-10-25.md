# Historical phase planning and execution notes

Archived 2026-10-25 from the implementation plan. Earlier status and
authorizations describe their original checkpoint. Use the [phase summary](../REPORT.md).

## Phase 10 — Replace temporary components incrementally

### 10.1 — Fresh CloudNativePG application databases

Status: **fresh installation and existing-image application checks complete**
(2026-10-23). The operator approved fresh empty
application databases and disposal of old DEV/STAGE/PROD database data. This
supersedes logical dump/restore and the earlier requirement to test legacy
backup restoration before this replacement. Jenkins and unrelated data remain
protected. Phase 9 deferred Jenkins work remains open and is not part of 10.1.

- [x] Inspect both original checkouts and live databases: PostgreSQL 16.6,
      `plpgsql` and `uuid-ossp`, `app` database, legacy `postgres` application
      login, 1 GiB local-path PVC per environment; capture private baselines.
- [x] Select compatible pinned CNPG 1.30.1 / PostgreSQL 16.15 images. Budget
      DEV/STAGE one instance each, PROD two instances on distinct nodes with
      asynchronous streaming replication, no synchronous replication. Per
      instance: 250m/512 MiB requests, 1 CPU/1 GiB limits, 2 GiB local-path.
- [x] Drain and hold conflicting Jenkins work; pause Argo roots and children.
      Use committed maintenance replicas and revision-bound explicit syncs.
- [x] Install the operator in both clusters; create fresh environment Clusters
      and bootstrap `app_owner` using existing passwords. Keep `postgres`
      administrative access and existing initialization login credentials.
- [x] Complete DEV, then STAGE, then PROD: database readiness, stable `db`
      endpoint, Alembic initialization, unchanged application digests, HTTPS,
      login and disposable CRUD; verify PROD streaming/async placement.
- [x] Retire only obsolete application database Deployments/config/PVCs after
      each replacement works; verify Argo ownership and reconciliation.
- [x] Restore approved Argo and Jenkins polling/publication settings, preserve
      unrelated Secrets/PVCs and Jenkins user/history inputs; record results.

Procedure: [fresh CNPG installation](../../../../../runbooks/18-cloudnative-pg.md).
Results: [Phase 10 report](cnpg-installation-2026-10-23.md). Existing-image validation is
required; full Jenkins CI/CD regression and vulnerability scans are not rerun
for this replacement. PROD image promotion remains blocked until Phase 9's
agreed automatic STAGE acceptance gate is implemented and verified.

### 10.2 — R2 physical backup and isolated PITR

Status: **completed on 2026-10-23 within the agreed Alertmanager-only boundary**.
Current CNPG data is to be
preserved; 10.1's disposable-data authorization has ended. Use the original
checkouts and unchanged application images. No full Jenkins regression or
Phase 9 feature work is included.

Confirmed configuration:

- Supported, digest-pinned Barman Cloud Plugin and cert-manager in both
  clusters. cert-manager issues only plugin internal TLS; Certbot/application
  certificates, DNS, ingress and routing remain unchanged.
- Private dedicated bucket `liora-backup`, destinations `dev/`, `stage/`,
  `prod/`, one bucket-scoped S3 pair. Prefixes are not credential isolation.
  Physical full backups and continuous WAL use lz4; no raw live-PVC copying.
- Barman recovery windows DEV/STAGE 7d, PROD 14d, retaining the anchor backup
  and required WAL. Do not add independent R2 age-deletion lifecycle rules.
- VM 250 owns a recoverable systemd coordinator: daily 02:00 UTC, strict
  PROD → STAGE → DEV order, next starts only after a terminal predecessor.
  Global durable locking and persisted intent cover timer/manual invocations
  and interruptions. A failed full backup alerts and advances without retry;
  running/unknown state alerts and blocks advancement. WAL is independent.
- Target RPO PROD 15m, DEV/STAGE 1h; target RTO PROD 1h, DEV/STAGE 4h from
  available K3s/R2 access to usable restored application. These need measured
  evidence. Set archive_timeout with upload-delay headroom.
- Integrate failure, overdue-backup, WAL, telemetry and recovery conditions
  with existing Prometheus/Alertmanager. Aggregate R2 usage warning >10 GiB
  is informational, not a quota or deletion trigger. No daily success messages.
  **Latest operator steering:** do not investigate/configure Slack or claim
  Slack delivery; that work belongs to another person. Alertmanager integration
  is this checkpoint's notification boundary. SMTP remains deferred.
- PITR DEV → STAGE → PROD, separate temporary namespaces/Clusters, at most
  one restored DB at a time. Include/exclude controlled markers around an
  explicit target using base backup plus archived WAL. Never change live
  endpoints. Restore configuration must neither archive to nor prune source.
- Document monthly manually initiated sequential isolated PITR for all three
  environments and after significant backup changes; no weekly restore timer.

- [x] Validate/store private R2 inputs; update checker, fake examples and
      credentials-table helper together; verify S3 operations without leaks.
- [x] Install bounded pinned dependencies and configure environment archives.
- [x] Hold/drain conflicting deployment work, preserve data, coordinate DB
      sidecar rolls and declarative backend reconnects, then verify live CRUD.
- [x] Complete full backups and verify continuous WAL and retention settings.
- [x] Install least-privilege VM 250 coordinator, durable locking, bounded
      API calls and monitoring; test failure/interruption/unknown-state paths.
- [x] Verify isolated PITR inclusion/exclusion, ownership/schema/application
      compatibility and measured RPO/RTO evidence in all environments.
- [x] Verify usage/Alertmanager integration, preserve evidence, clean only test
      resources and restore the exact approved Argo/Jenkins automation.

Procedure: [runbook 19](../../../../../runbooks/19-cnpg-r2-backup-pitr.md).
Results: [Phase 10.2 report](r2-backup-pitr-2026-10-23.md). Readiness requires successful
restore checks; configured schedules alone do not prove recovery windows or
RPO/RTO. Delegated Phase 9 work and PROD promotion gate remain separate.

Measured PITR application usability: DEV 286.163s, STAGE 195.483s, PROD
287.029s. Natural WAL delivery: 303.059s, 304.031s, 304.043s respectively.
The full VM 250 sequence and cross-host overlap refusal passed. Its 02:00 UTC
timer is enabled; the owner subsequently confirmed that the overnight run
produced new archives in R2. This confirms observed scheduled backup output,
not an additional restore test or a review of every coordinator terminal state.
Original Argo/Jenkins policies and main polling are restored.
All 13 original PVCs, current data and application images were preserved.
Slack delivery is delegated; bucket-policy metadata inspection remains limited
by 403 responses. Full 7/14-day archive coverage requires elapsed retention
history. Continue monthly manual isolated PITR and repeat after mechanism
changes. These database checks do not complete the separate PROD image gate.

### Other separately scoped improvements

- [ ] Review automatic stale SQLAlchemy connection handling in a separate
      application change. Until then, coordinate backend reconnect rollouts
      after database/operator restarts as documented in runbook 18. This does
      not require an application rebuild for the completed 10.1 checkpoint.
- [ ] Reconcile the remaining ADR backlog; refine resource budgets and approve
      logging, alert delivery, HPA/PDB and the private recovery kit
      before implementing them. External uptime and certificate monitoring for
      all three application domains is already provided by UptimeRobot, as
      confirmed by the owner.
- [ ] Align the recovery validator/examples with the current private-input
      model: retire mandatory legacy controller-key fields through a deliberate
      schema update while preserving older recovery archives. No controller or
      Git-managed encrypted Secret payloads are part of the target design.
- Private Adminer remains approved for DEV/STAGE/PROD. Review possible removal
  from PROD in one to two years after sustained stability, when direct
  interventions are exceptional and an alternative operational path exists.
- Optional only: for a substantially larger production deployment, reassess
  HAProxy's single point of failure, public IP availability and a redundant edge
  design. Keep the current HAProxy → Traefik ServiceLB node-pool path; there is
  no dedicated ingress-VIP implementation task.

**10.1 pass:** fresh databases and existing-image application checks succeed in
all three environments; obsolete DB resources are retired and approved
reconciliation/automation restored. This does not close Phase 9 or establish
backup/recovery readiness.
