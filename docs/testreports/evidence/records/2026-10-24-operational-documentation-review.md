# Operational documentation review — 2026-10-24

Historical checkpoint. Later [Phase 9 evidence](../../phases/phase-09/REPORT.md) supersedes the
observer/promotion implementation gaps. [Etcd evidence](2026-10-25-etcd-r2-backups.md)
supersedes the off-host snapshot implementation gap. Full recovery remains unverified.


## Scope

Documentation-only restructuring around fresh installation, disaster recovery
and ongoing backup/recovery. No Kubernetes resources, database data, Jenkins
settings, DNS, credentials, application code or operator-script execution logic changed. The launcher's
missing-environment diagnostic points to the consolidated tool runbook.
Original checkouts and private operator data remain in place.

Permanent manuals use English, ordered checklists, explicit execution location,
preconditions, stop conditions and completion criteria. Historical results and
migration-specific permissions are preserved here rather than prescribed as
installation requirements. Desired architecture does not claim execution proof.

## Scenario corrections

- Fresh installation explicitly initializes empty CNPG databases. Its dependency
  order includes namespaces, CNPG, cert-manager/Barman, R2 credentials and public
  issuers before dependent custom resources/application initialization.
- Recovery rebuilds shared infrastructure using the installation runbooks, then
  holds application initialization until a selected data recovery route is ready.
  Empty initdb is not a data restore. Database restoration and application HTTPS/
  login/CRUD form separate gates before automation resumes.
- Routine operations cover daily/manual coordinated base backups, WAL health,
  interruption/resume, usage alerts, monthly isolated PITR and cleanup.
- R2 database backup coverage is separated from Jenkins home, infrastructure
  state, cluster snapshots, private credentials and monitoring storage.
- Permanent Argo access uses Admin VIPs. The diagnostic Slack helper's temporary
  loopback requirement remains explicit and is not a permanent access dependency.

## Recovery capability register

| Capability | Implementation/evidence | Remaining work or boundary |
| --- | --- | --- |
| Empty CNPG installation | Phase 10.1: DEV/STAGE/PROD and existing-image application checks completed. | Do not repeat the historical destructive replacement for ordinary deployment/recovery. |
| Physical backups and WAL to R2 | Phase 10.2 implemented per-environment archives, retention and coordinator. | Maintain elapsed-window coverage, off-host credentials and routine monitoring. |
| Isolated PITR with application compatibility | Phase 10.2 demonstrated target inclusion/exclusion and browser CRUD in all environments. | Monthly sequential exercise and repeat after mechanism changes. |
| Backup-cycle interruption recovery | Incident 2026-10-24 resumed the retained cycle without retrying terminal backups or clearing the Lease. | Reusable response is now in runbook 19; incident-specific resource IDs stay in its report. |
| Full application disaster restore into a rebuilt live environment | Infrastructure rebuild and isolated restoration primitives exist. | Exercise the documented live recovery bootstrap, stable endpoint/GitOps cutover, post-recovery archive identity and application release route. The isolated verification helper hardcodes original archive identities; adapt its source selection before using it after an archive-identity change. Isolated `pitr.py` is not this procedure. No full live DR completion is claimed. |
| Jenkins state preservation and transfer | Phase 9 retained users/history/encryption material and current K3s administrator during the one-time transfer. | A generic stopped-current-K3s-home backup/restore procedure and exercise remain separate from the legacy-aware helpers. The manual contains a preservation/recovery checklist, not a claim of automated generic restoration. |
| Jenkins fresh service foundation | Controller/credential manifests exist. | Complete reproducible fresh agent/job installation independent of restored-home markers. The existing composed agents overlay expects the retained migrated home. |
| K3s snapshot restoration | Installation runbook links the upstream snapshot/token procedure. | Full project-specific off-host etcd backup capture, retrieval and restore exercise must be documented/verified separately. A fresh K3s installation does not restore etcd. |
| Infrastructure module state | Terraform modules and input/state handling exist. | Final off-host kit assembly, state recovery choices and full host rebuild exercise remain explicit work. |
| Secrets and external configuration | Recovery schema, fake examples and secret-safe helpers exist. | Preserve GitHub installation settings, Slack webhook bindings and all private platform records off-host; Git cannot recover those values. |
| Monitoring configuration | Helm/manifests restore rules/dashboards/configuration. | Historical Prometheus/Alertmanager PVC data has no database-R2 restore procedure. Do not imply it is covered by PostgreSQL backups. |
| Public certificates | Phase 11 cert-manager/DNS-01 and served-certificate checks completed. | Restore the DNS credential and reissue; an old edge private key is not required. |

The owner confirmed that disaster recovery must prescribe restoring application
PostgreSQL from R2 into the rebuilt environment, with rebuild/prerequisites
documented now. The recovery navigator describes recovery bootstrap and release
gates without calling isolated PITR the live restore procedure. Isolated PITR
commands and natural-WAL verification now live outside runbooks in
[backup verification](../../../operations/POSTGRESQL_BACKUP_VERIFICATION.md). This
documentation does not claim a newly executed live disaster restore.

## Historical procedure preservation

The following snapshots retain the prior text in full (including original
commands, limitations and execution observations), with local links adjusted:

| Original location | Historical record |
| --- | --- |
| runbook 03 | [Template procedures](../../archive/migration-procedures/phase0-template-procedures-archive.md) |
| runbook 07 | [Router procedures](../../archive/migration-procedures/phase1-router-procedures-archive.md) |
| runbook 08 incident commands | [Clone recovery](../../archive/migration-procedures/phase1-vm-clone-recovery-archive.md) |
| runbook 13 | [Application phase 3–5 procedures](../../archive/migration-procedures/phase3-5-application-procedures-archive.md) |
| runbook 14 | [GitOps phase 6 procedures](../../archive/migration-procedures/phase6-gitops-procedures-archive.md) |
| runbook 15 | [Certificate phase 11 procedures](../../archive/migration-procedures/phase11-certificate-procedures-archive.md) |
| runbook 16 | [Platform phase 8 procedures](../../archive/migration-procedures/phase8-platform-procedures-archive.md) |
| runbook 17 | [Jenkins phase 9 procedures](../../archive/migration-procedures/phase9-jenkins-procedures-archive.md) |
| runbook 18 | [Database transition](../../archive/migration-procedures/phase10-database-transition-archive.md) |
| runbook 19 | [Backup implementation procedures](../../archive/migration-procedures/phase10-2-backup-procedures-archive.md) |
| Grafana operations history | [Dashboard execution](../../archive/migration-procedures/phase8-grafana-execution-archive.md) |
| Slack operations history | [Alerting execution](../../archive/migration-procedures/phase8-alerting-execution-archive.md) |

The dated [Slack deployment report](2026-10-23-slack-alerting-deployment.md)
moved from `docs/operations/` into this reports directory. Grafana execution
JSON and screenshots moved into this directory's `evidence/` and `screenshots/`
subdirectories; links in the presentation/reference documents were updated. Existing incident,
phase and acceptance reports remain historical records. No operator script was removed or functionally rewritten; migration-only helpers remain linked from their archived procedure.

## Jenkins documentation boundary

The preceding read-only review observed main #23 SUCCESS, publisher #42 with an
accepted STAGE receipt for application `cce22bf`, and manual DEV publisher #43/
#44 SUCCESS. The live publisher holds its lock through observation/receipt and
uses `jenkins-publisher-ci-c6a70f44808d`. These supersede older claims that the
observer and DEV entrypoint are absent, but do not prove every pending failure/
concurrency scenario or finish PROD promotion.

The same review observed the startup quiet-mode/queue-clear hook still present,
nightly main scheduling and recurring indexing active, and historical PR jobs
enabled. The plan's historical main-only policy differs from that snapshot.
This documentation task does not approve, disable or enable those settings.
Desired architecture keeps the agreed scheduling policy; runtime-policy
reconciliation remains Phase 9 work. `PROD_ENABLED=False` remains the source
safety block. Manual rollback/restart and generic Jenkins recovery exercises
are not marked complete by this documentation rewrite.

## Validation

Validation passed for 54 changed/new Markdown documents: 501 local links and heading anchors
resolve, fences balance, and 87 shell blocks pass `bash -n`.
Seven moved Grafana evidence files retain identical SHA-256 content. Operational
runbooks/architecture pass English and historical/educational-framing checks;
`git diff --check` passes. Operator-script execution logic remains unchanged; only the launcher's
documentation path was updated. The application
checkout is clean and unchanged by this task. The unrelated untracked
`docs/project-schemes.drawio` is preserved and excluded from these commits. No infrastructure apply, Jenkins build, database fault,
publication, deployment or recovery exercise is part of this change.

## Networking and workspace consolidation

Repository first/join server playbooks retain K3s defaults: no alternate CNI,
Flannel disable flag or network-policy disable flag is configured. The desired
architecture now names Flannel VXLAN and K3s's embedded kube-router-netpol
controller, with namespace-scoped Jenkins policies. This is a repository
configuration review, not a new live dataplane/enforcement exercise.

The former Cilium discussion is preserved in
[historical network alternatives](../../decisions/cilium-alternative.md).
`docs/CILIUM.md` is removed.

`docs/LOCAL_WORKSPACE.md` is removed after consolidating tool/environment setup
in runbook 11, private-data handling in recovery inputs and historical paths in
[the workspace report](local-workspace-report.md). All Markdown references are
retargeted. `scripts/local-python.sh` changes only its missing-environment
diagnostic documentation path; its commands, environment variables and execution
behavior are preserved. No tool was installed or runtime configuration changed.
