# Verify PostgreSQL backup recovery

**Where:** Management VM 200, infrastructure repository root.
**Purpose:** Isolated backup verification. Do not switch live application endpoints.
**Frequency:** Monthly and after significant changes to backup mechanisms.

## Preconditions

- [ ] Confirm completed physical backups and working WAL archiving using [backup operations](../../runbooks/19-cnpg-r2-backup-pitr.md).
- [ ] Preserve live database contents, credentials and image digest pairs.
- [ ] Run DEV, then STAGE, then PROD with only one temporary restored instance at a time.
- [ ] Retain failure evidence and stop before advancing to the next environment.

## 1. Run an isolated PITR exercise

- [ ] Run monthly and after significant backup changes, sequentially DEV → STAGE → PROD.
- [ ] Require one temporary restored database instance at a time and sufficient local storage.
- [ ] Select a completed Backup resource in each source namespace.
- [ ] Prepare pinned Python/backup dependencies and Chromium using the [workspace guide](../../runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
- [ ] Create a new protected evidence directory and enter the selected Backup resource names:

```sh
umask 077
evidence="$PWD/.local-work/private/pitr/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$evidence"
read -r -p 'DEV Backup resource name: ' dev_backup
read -r -p 'STAGE Backup resource name: ' stage_backup
read -r -p 'PROD Backup resource name: ' prod_backup
bash scripts/local-python.sh scripts/backups/pitr.py --environment dev --backup "$dev_backup" --evidence "$evidence/dev"
```

Standalone script: [pitr.py](../../scripts/backups/pitr.py).

- [ ] Require DEV result `success: true` and `cleanup_complete: true`; inspect its target, inclusion/exclusion and application results before continuing.

```sh
bash scripts/local-python.sh scripts/backups/pitr.py --environment stage --backup "$stage_backup" --evidence "$evidence/stage"
```

- [ ] Require STAGE success and cleanup before PROD:

```sh
bash scripts/local-python.sh scripts/backups/pitr.py --environment prod --backup "$prod_backup" --evidence "$evidence/prod"
```

The helper commits controlled source markers around an explicit UTC target,
archives their WAL, restores a physical backup plus WAL into a new namespace,
and checks owner/schema and existing-image browser login/CRUD. Live `db`
endpoints remain unchanged. The restored Cluster has no archiver plugin and its
ObjectStore has no retention policy. Shared source credentials still require
careful configuration isolation.

- [ ] Record physical backup ID, recovery target, included/excluded markers, ownership/migration checks, image IDs, application usability time and cleanup.
- [ ] Compare measured results to RTO objectives: PROD 1 hour; DEV/STAGE 4 hours. The helper clock includes marker/WAL preparation through usable restored application; infrastructure rebuild and cleanup after usability are excluded.
- [ ] On failure, stop before the next environment. Preserve diagnostics and the temporary resources.
- [ ] Clean only the recorded namespace/UID and source marker after inspection:

```sh
bash scripts/local-python.sh scripts/backups/pitr-cleanup.py --record "$evidence/dev/result.json"
```

Standalone script: [pitr-cleanup.py](../../scripts/backups/pitr-cleanup.py).
Select the matching environment record. Do not invent missing identities or use
wildcard namespace/PVC deletion. Isolated PITR is an exercise; it does not switch
a restored database into the live application.

## 2. Measure natural WAL delivery

- [ ] Select an environment and a protected evidence directory.
- [ ] Start and observe a committed marker without forcing its WAL segment:

```sh
bash scripts/local-python.sh scripts/backups/rpo.py start --environment "$environment" --record "$evidence/natural-rpo.json"
bash scripts/local-python.sh scripts/backups/rpo.py wait --environment "$environment" --record "$evidence/natural-rpo.json"
```

Standalone script: [rpo.py](../../scripts/backups/rpo.py).

- [ ] Do not switch the measured WAL or start a full backup for that environment until observation ends.
- [ ] Compare acknowledged commit-to-R2 delivery with RPO objectives: PROD 15 minutes; DEV/STAGE 1 hour. Keep the measured sample and matching marker cleanup record.


## Completion record

- [ ] Record backup ID, explicit UTC target, marker inclusion/exclusion, database/schema ownership, application digest pair and login/CRUD outcome.
- [ ] Record measured recovery time and natural WAL-delivery sample separately.
- [ ] Confirm temporary-resource cleanup and unchanged live endpoints/data.
- [ ] Store sanitized execution results under `docs/testreports/`; keep raw private evidence outside Git.

**Done when:** Each environment's physical-backup-plus-WAL restore passes its target/data/application checks and exact temporary resources are removed.

For rebuilding and restoring the actual service, use [disaster recovery](../../01-Disaster_recovery.md).
