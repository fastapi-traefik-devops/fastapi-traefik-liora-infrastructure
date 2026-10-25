# Operational documentation closure — 2026-10-25

Historical checkpoint. Later [Phase 9 evidence](../../phases/phase-09/REPORT.md) supersedes the
observer/promotion implementation gaps. [Etcd evidence](2026-10-25-etcd-r2-backups.md)
supersedes the off-host snapshot implementation gap. Full recovery remains unverified.


## Scope and result

Reviewed the current installation/recovery navigators, platform and database
runbooks, completed Jenkins controller/agent procedures, CI/CD documentation,
recovery ZIP tooling and manifest documentation. No live deployment, database
restore, Jenkins/Argo change, image build or credential rotation was performed.

## Gaps addressed

- Backup coordinator: added a separate old-profile preservation, RBAC/token/CA
  regeneration, read-only API check and VM 250 installation route. The API
  check does not create Backup objects or initialize a database.
- HTTPS: recovery prepares edge/DNS/issuers before data restoration, then
  issues the selected Certificate and publishes HTTPS after workload startup
  and before login/CRUD acceptance. Fresh installation uses its manual overlay
  until later Argo adoption.
- Jenkins: moved the one-time manifest history here; renamed runbook 17 for
  reusable operation; put SCM, credential scope, publisher definition, pin,
  Declarative validation and script approval in runbook 27. Runbooks 22/23
  remain the controller/agent procedures.
- Database/monitoring: added exact Grafana record/Secret order and a focused
  database-maintenance procedure that records and restores original Argo and
  Jenkins policy while preserving data and image digests.
- Recovery kit: documented capture, existing AES ZIP encryption, off-host
  copy, retrieval, checksum, extraction and placement. A staging helper copies
  required ignored Terraform state, protected platform records and a stopped
  Jenkins backup into `recovery/` for the existing ZIP helper. R2/WAL, etcd
  snapshots and PVC contents remain outside the ZIP.

## Local checks

- Synthetic capture fixtures covered required state, protected records,
  complete Jenkins archive, refusal to overwrite, missing input, symlink
  rejection and checksum mismatch.
- Synthetic archive-inventory fixtures confirmed that untracked kit/state/
  Jenkins files are selected while Git-tracked documentation is excluded.
- Coordinator access fixtures confirmed only read-only BackupList and Lease
  requests for both clusters, without a database.
- A synthetic overlay fixture confirmed that the database reconnect helper
  adds one annotation patch and retains the backend digest.
- Checked shell syntax, changed Markdown paths/anchors, referenced script
  options and manifest names, and `git diff --check`.

The AES ZIP creation/decryption itself was not run locally: the pinned
`pyzipper` dependency is unavailable in this environment and package access
was unavailable. The existing encryption implementation was retained; the
synthetic checks validate its shared file-selection logic, not encryption.

## Remaining decisions and live checks

- The observer manifest names `jenkins-acceptance-ci-8b584055a83c`, while the
  current bundle helper emits `jenkins-acceptance-ci-9c2084ceb24c`.
  `deploy-jenkins-agents.py` installs only two workers and does not provision
  `jenkins-acceptance/stage-observer-connection`. Pin alignment, a bounded
  Secret installer and the approved activation policy are required before
  enabling the observer on a rebuilt controller. PROD
  promotion stays blocked there until automatic acceptance for the exact
  SHA/digest pair is implemented and verified.
- In an approved live recovery exercise, verify the new coordinator token/CA
  route and VM 250 inspection, preserved Grafana login, Jenkins job/observer
  behavior, HTTPS and real application login/CRUD. Documentation and fixture
  tests do not prove full disaster recovery.
