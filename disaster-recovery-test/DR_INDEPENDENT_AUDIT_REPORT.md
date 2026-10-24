# Independent disaster recovery audit and publication review

Audit date: 24 October 2026. Runtime exercise: approximately 09:49–10:15 Europe/Tirane
(UTC+02:00). Publication recheck: 09:16 UTC. Reviewer: Codex, reviewing retained
command/API evidence against source and executing additional local checks.
This is an evidence review, not a third-party certification or a fresh full DR run.

## Conclusion

The saved evidence supports real, scoped local tests of Kubernetes persistence,
Argo reconciliation, monitoring, synthetic Jenkins home restoration, and workload
and PostgreSQL logical rollback. It does **not** support a complete independent
rebuild of Liora, physical R2 restoration, PITR, original application acceptance,
or Proxmox recovery. Missing recovery inputs remain explicit blockers.

- [Full runtime report](LOCAL_DISASTER_RECOVERY_TEST_REPORT.md)
- [Evidence index](astra-review/INDEX.md)
- [Presentation selections](DR_PRESENTATION_FINAL_EVIDENCE.md)
- [Source provenance, timestamps and artifact hashes](astra-review/source-provenance.json)
- [Publication validation](astra-review/test-results/package-validation.json)

## Source and environment

Runtime source infrastructure: `ff154ae7a81858f5dcdf49d0582cb1d1074a6943`.
Application: `7aaf28740b227fee925e23383d6d589a3ea35336`.
Publication was prepared on latest main `06c62f86cc691ff171f7ab8555fa79caf2526194`,
including the subsequent TLS cutover and concurrent Jenkins changes. Those changes
are retained, not reverted. The local runtime run does not validate the later TLS cutover.

The disposable Docker/k3d environment had 8 logical CPUs and 7.6 GiB RAM,
initially about 2.1–2.3 GiB available. Components ran sequentially. K3s was
1.35.5+k3s1, a cached version differing from source platform 1.36.5. The private
lab API bound to 127.0.0.1:16443; exact kube-system UID was
`aa85f393-9b41-42a5-af6a-7fadfc783683`. Detailed component versions, resource caps
and timing boundaries are in the runtime report. This is a single-node local
scope, without HA, disk-loss or site-loss coverage.

## Findings and dispositions

| Finding | Evidence / consequence | Disposition |
|---|---|---|
| R2 recovery input unavailable | No protected physical backup/WAL or verified read-only R2 identity. Operator readiness cannot prove restoration. | BLOCKED. Obtain those inputs before a new isolated restore. Existing writer/delete identities were not used. |
| Exact application images unavailable anonymously | Actual GHCR 401 for pinned backend/frontend digests. No recovered DB. | BLOCKED. Need authorized read-only image access and recovered data before migrations/login/CRUD acceptance. |
| Zero replicas can report successful rollout | Application startup log contains success after deployments were scaled to zero. Events show actual pull failure. | Corrected interpretation in reports; new verifier explicitly rejects zero replicas and incomplete/stale deployments. |
| Recorded runners can overwrite evidence | Original one-off shell/Python runners open fixed log/result paths for writing. | Preserve as historical source snapshots; new verifier requires a new output directory outside the repository, before any runtime query. |
| Dependency runner can mask a failure | Recorded test02.sh uses set -u and records rollout status but can finish with a later successful command. | New verifier propagates command failures and verifies every dependency deployment. Recorded logs remain unchanged. |
| Storage runner prints but does not assert marker | Recorded test01.sh exposes marker output; rollback runner subsequently asserts preservation and UID. | New verifier checks exact cluster UID, Bound PVCs, available deployment and exact marker; no success inferred from printed text alone. |
| Python assert can disappear under optimization | Original rollback/cleanup runners rely on assert. | New verifier uses explicit runtime failures, tested under normal and optimized Python. Historical sources retained. |
| Argo result is narrowly scoped | Real ConfigMap sync succeeded; original DEV/STAGE definitions were held. | PASS only for controller startup/adapted definitions and one ConfigMap reconciliation. |
| Monitoring lacks original exporters/history | Real self-scrape is UP; 30 rules evaluate; recovered dashboards show absent telemetry. | PASS only for config/runtime and local alert lifecycle. No production notification delivery or historical TSDB recovery claim. |
| Jenkins source is synthetic | Actual archive, keys, disabled job and second controller restore; original plugins/history unavailable. | PASS for synthetic core controller state. Latest-main staging helper independently passes 12 fixture tests. |
| PostgreSQL rollback is logical | pg_dump/pg_restore of one synthetic table, not physical restore/WAL. | PASS for table checkpoint only; never labeled R2/PITR. |
| Screenshot duplication | 25 capture files contain 24 unique SHA-256 values; first two Kubernetes captures are identical. | Publish 24 originals once. Preserve original local files and record both source names in provenance. |
| Historical/generated pictures can be mistaken for new runtime evidence | Existing simulation images are explicitly labeled. | Preserve them separately. No new simulated image is included in the 24 unique runtime screenshots. |

## Real results accepted by this review

| Test | Accepted result | Direct evidence |
|---|---|---|
| Kubernetes/storage | PASS: API/node and scheduling worked; Bound PVC marker survived actual pod replacement and node stop/start. | [Storage proof](evidence/real/2026-10-24-local/01-kubernetes/storage-proof.log), [rollback](evidence/real/2026-10-24-local/07-rollback/results.json) |
| CNPG/R2 | PARTIAL: operator, cert-manager, Barman startup passed; physical recovery BLOCKED. | [Dependency log](evidence/real/2026-10-24-local/02-cloudnativepg-r2/dependencies.log), [missing inputs](evidence/real/2026-10-24-local/02-cloudnativepg-r2/input-preflight.json) |
| Application | BLOCKED: real attempts failed image authorization; no migrations/auth/CRUD recovery verified. | [Actual pull events](evidence/real/2026-10-24-local/03-application/events.log) |
| Argo CD | PASS, limited: actual local ConfigMap sync became Synced/Healthy. | [Successful retry](evidence/real/2026-10-24-local/04-argocd/sync-retry.log) |
| Monitoring | PASS, limited: 30 healthy rules, live up=1, dashboard import, synthetic alert firing then resolved. | [Rules](evidence/real/2026-10-24-local/05-monitoring/rules.json), [metric](evidence/real/2026-10-24-local/05-monitoring/query.json), [resolved](evidence/real/2026-10-24-local/05-monitoring/alertmanager-resolved.json) |
| Jenkins | PASS, synthetic state: real home archive staged/restored, marker decrypted, disabled job, zero executors, quiet mode. | [Archive receipt](evidence/real/2026-10-24-local/06-jenkins/archive-receipt.json), [restored runtime](evidence/real/2026-10-24-local/06-jenkins/restored-runtime.json), [startup verification](evidence/real/2026-10-24-local/06-jenkins/restored-startup.log) |
| Rollback | PASS: actual HTTP v1 → v2 → v1 and exact SQL baseline restored. 2.204s workload; 0.602s logical table rollback. | [Recorded commands](evidence/real/2026-10-24-local/07-rollback/rollback.log), [structured result](evidence/real/2026-10-24-local/07-rollback/results.json) |
| Cleanup | PASS: owned lab stopped, original containers/mounts retained, original default context preserved. | [Original receipt](evidence/real/2026-10-24-local/08-cleanup/receipt.json), [new read-only recheck](astra-review/test-results/stopped-lab-recheck.json) |

Initial failures are retained: k3d creation/image import, over-broad lab egress
policy affecting CNPG, static HTTP Git EOF, and Alpine lacking httpd. Successful
retries are identified explicitly. They do not convert the unresolved R2/application
blockers into success. The 36.926s combined successful rollback run excludes the
failed attempt and cluster restart; none of these numbers is full-platform RTO/RPO.

## Improvements and additional checks

Added [verify_local_lab.py](astra-review/scripts/verify_local_lab.py), a read-only
verifier that never starts/stops resources or modifies Kubernetes. It rejects a
wrong cluster before further running-mode queries, propagates failed commands,
rejects zero replicas/stale/incomplete rollouts, asserts PVC/marker state, and
refuses existing or repository-local output directories. It writes a timestamped
PASS/FAIL record and returns a nonzero status on failure without emitting raw
credential-bearing command diagnostics.

Eight regression tests cover wrong target, command failure, zero replicas, stale
controller generation, partial rollout, a running original container, evidence
preservation and persisted failure/nonzero exit. They pass under normal and
optimized Python. [Test log](astra-review/test-results/verifier-regressions.log).
The stopped-mode verifier passed against the actual retained local resources.
The new running-mode verifier was not run against a restarted cluster; its guards
were regression-tested. Runtime success evidence remains the original executed logs.

The latest-main Jenkins staging helper is byte-identical to the helper used during
runtime (SHA-256 `aca0a70f28b54c1145bf46a1dc64f15f66a67577da4db193f1a66545678fc8bd`).
All 12 archive fixture tests passed on disposable copies: [log](astra-review/test-results/latest-main-jenkins-fixtures.log),
[provenance](astra-review/test-results/latest-main-jenkins-fixtures.json).
Original production/helper/test scripts were not edited.

## Preservation and publication safety

All new work is under disaster-recovery-test/. Existing report, scripts,
screenshots and recorded results remain intact. Only navigation sections are
appended to the existing README/index; their two checksum entries are refreshed.
Original navigation hashes remain in the publication base commit. All other
historical checksums are unchanged and verified.

The new logs retain original timestamps and original terminal whitespace/ANSI formatting;
Git whitespace checks exclude these recorded .log files to preserve their evidence bytes. Home-directory usernames in text logs
are replaced by /home/local-user; source and published hashes plus source file
modification times are recorded. Screenshots are unmodified genuine captures,
visually inspected and decoded as JPEGs. Product UI views and rendered saved-log
views are identified separately. No original historical screenshot was duplicated.

Only allowlisted public logs/JSON, reports, screenshots, authored scripts and
small fixture configs are included. No passwords, tokens, private keys, kubeconfig,
database dumps, Terraform state, controller homes, credential/recovery archives,
Git fixture history or ZIP bundles are committed. Generic credential-pattern
checks and exact matching against locally generated private values are performed
without printing those values. This is a scoped scan, not a claim that every
possible secret format is automatically recognizable.

No production infrastructure, R2 data, DNS, certificate, pipeline or notification
endpoint was changed by this exercise. Local state did change: three originally
running Jenkins containers were stopped at the user's request; disposable lab
resources were created and stopped. Their existing volumes remain attached. Thus
"existing infrastructure untouched" applies to production configuration/data and
preserved original assets, not to local running/stopped state. The publication
recheck found all Docker containers stopped and the original context unchanged.
