# Historical recovery planning notes

Archived 2026-10-25 from the implementation plan.
Use the [active plan](../../IMPLEMENTATION_PLAN.md) for remaining work.

## Operational documentation and full recovery completion

- [x] Separate permanent fresh deployment, disaster recovery and backup/PITR operating procedures.
- [x] Preserve migration-specific commands and evidence under `docs/testreports/`; retain operator scripts.
- [x] Remove historical status/educational framing from operational runbooks and desired architecture.
- [x] Provide live CNPG recovery preparation and etcd snapshot recovery procedures with protected inputs, source archive separation, workload holds and resumable local tooling. See [recovery runbook implementation](2026-10-25-recovery-runbooks.md).
- [ ] Exercise live CNPG restore/cutover and the three-server etcd restore route in a separate recovery checkpoint. Verify the selected target, stable endpoint, ownership, post-recovery archive, original-token decryption and application checks; local checks are not a live recovery exercise.
- [x] Adapt current-K3s Jenkins stopped-home backup/restore and two-worker connection helpers to preserve the archived administrator and selected home without migration receipts. Add runbooks 22/23 and local safety checks. See [Jenkins recovery procedures](2026-10-25-jenkins-recovery-runbooks.md).
- [ ] Perform the isolated held-controller runtime restore checkpoint: verify login, credential decryption, retained history and agent connectivity without CI/publication/deployment. Complete the separate reproducible job bootstrap and acceptance activation work under Phase 9.
- [ ] Execute project-specific off-host etcd/state/private-kit retrieval and a
      full-system disaster recovery exercise; local capture fixtures are not
      an off-host restore.
- [ ] Record monitoring history coverage explicitly; PostgreSQL R2 backups do not restore Prometheus/Alertmanager volume data.

These remaining capabilities are not inferred from successful isolated PITR,
controller migration, or local recovery-tool validation.

### Operational runbook closure — 2026-10-25

- [x] Document coordinator RBAC/token/CA replacement with old-profile
      preservation and read-only inspection before any cycle.
- [x] Put DNS/issuer preparation before recovery, then certificate issuance and
      HTTPS publication after workload startup and before HTTPS acceptance.
- [x] Consolidate Jenkins job settings, credential scopes, publisher pinning
      and script approval in one operator procedure; keep migration history in
      `docs/testreports/`.
- [x] Document Grafana record placement, declarative database maintenance and
      exact automation-policy restoration.
- [x] Stage ignored Terraform state, platform records and a stopped Jenkins
      archive explicitly for the existing AES ZIP flow. Validate selection and
      integrity checks with synthetic fixtures.
- [ ] Align the observer bundle pin with its manifest and the reviewed
      publisher definition before activating it on a rebuilt controller. The
      current manifest references `8b584055a83c`, while the bundle helper
      selects `9c2084ceb24c`. Add the missing bounded installer for
      `stage-observer-connection`; retain the approved live delivery policy.
- [ ] Verify the reconstructed coordinator, Grafana login, Jenkins jobs and
      observer on live replacement clusters in a separate approved exercise.
      Local documentation and fixture tests do not prove recovery.


### Native embedded-etcd snapshots to R2 — 2026-10-25

- [x] Reuse native K3s snapshot/S3 support, existing bucket-scoped access and
      separate `etcd/nonprod/` / `etcd/prod/` destinations.
- [x] Configure all six servers sequentially: staggered 03:xx/15:xx UTC schedules,
      five local files per node and 42 R2 files per cluster prefix, with native ZIP.
- [x] Verify controlled uploads, downloads, ZIP/etcd checksums and matching
      cluster/token metadata without restoring any datastore.
- [x] Reuse VM 250 bucket telemetry and existing Alertmanager delivery for native
      failure and 14-hour R2-freshness alerts; preserve PostgreSQL/WAL operation.
- [x] Keep etcd restore outside the required standard DR sequence; document data
      coverage, count-based retention and token rotation independently.
- [x] Observe all six native recurring uploads at 15:00/02/04 and 15:10/12/14 UTC
      and ingest their R2 freshness into healthy live alerts.
- [x] Save actual current tokens at `recovery/k3s-nonprod-server.token` and
      `recovery/k3s-prod-server.token` (Git-ignored, `0600`); include capture in
      fresh setup and retain snapshot-free node metadata.
- [x] Remove only identified local snapshot/verification copies from `recovery/`
      after preserving tokens/identities; keep node/R2 snapshots unchanged.
- [x] Update validation and fake examples for fixed secure-token files; leave
      the owner's existing encrypted-archive helper unchanged.
- [ ] Owner: create the updated archive with `recovery/make_recovery_backup.sh`
      and keep its copy outside the host. No separate destination/password file
      is part of this implementation.

Evidence: [etcd R2 implementation report](2026-10-25-etcd-r2-backups.md).
Upload/integrity checks do not complete an etcd restore or full-system DR exercise.
