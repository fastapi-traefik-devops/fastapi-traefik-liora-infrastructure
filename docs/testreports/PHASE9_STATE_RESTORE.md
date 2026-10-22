# Phase 9 — Held Jenkins state restore

Date: 2026-10-22. **State restore verified; working CI remains inactive.**
Source application checkout remains read-only at
`b98a22e48527c256193ed65c10307eb574b27ab6`. Pipeline behavior changes remain
deferred to operator review. This report supplements [Phase 9](PHASE9_REPORT.md).

## Implemented transfer

Restored the validated stopped-source home into new 5Gi PVC
`jenkins-home-migrated` on `k3s-1-03`, retaining original `jenkins-home` for
rollback. Before writing the new volume, the foundation was stopped and its
home backed up consistently through a read-only mount. Original and new volumes
are retained, as is the completed bounded transfer Pod. Controller image, core
version, heap/resources and native address remain unchanged.

Private evidence is `.local-work/private/phase9/restore-20261022T103420Z/`:
original Deployment, apply-ready rollback object, current admin XML, staged
archive and per-file hashes, consistent foundation backup/hash receipt, transfer
receipt and `runtime-acceptance.json`. Directory/files are 0700/0600. No raw XML,
password hashes, credential values, keys or archives were added to Git.

The current K3s admin profile replaced the legacy admin profile at its source
salted path, preserving the original user-directory HMAC key. The foundation
login Secret was unchanged; migration JCasC has no user/password declaration.
The existing password authenticates through the API and browser; its stored hash
matches the current pre-transfer hash exactly. Legacy admin data remains in
the untouched recovery backup only. Non-admin user files were retained.

| Check | Result |
| --- | --- |
| File integrity before startup | All 6,372 restored files match the staged archive |
| Configured items | 30: 28 Pipeline jobs, one multibranch project and one plain folder |
| Build records | 139; zero currently running |
| Persisted users | Three: retained current admin and two source users |
| Runtime-only identity | `SYSTEM` also appears transiently; it is not an extra persisted account |
| Stored credentials | Original `app-ci/github-ci-app`, `trusted/ghcr-write`, `trusted/gitops-app` scopes/IDs retained |
| Credential decryption | Both App private keys and registry password present; values never printed |
| Original keys | Master key, `hudson.util.Secret` and user-directory HMAC key match staged hashes |
| Plugins | All 84 locked versions match; 85 loaded including already-preserved `locale`; zero failed plugins |
| Hold | Quiet; zero controller executors, agents, queue items and running builds; jobs/scanning/resume disabled |
| Egress | The same public-IP probe succeeded before the selected deny policy and failed afterward |
| Admin login | Existing password passes API and native browser at `http://192.168.77.16:8085`; hash unchanged |

All job sources remain preserved without promotion redesign. The original
application checkout is unchanged, and canonical comparison of all 28 Pipeline
definition elements matches the stopped-source archive. Disabled execution, trigger removal and
resume blocking affect the migration copy only. Startup may finalize previously
interrupted Pipeline statuses with resume disabled; no new build was scheduled
by the helpers. Original interrupted state remains in the source backup.

## Startup and recovery boundaries

The `held/` overlay uses the separate restored home, a quiet-mode hook and an
egress policy selected only for the Jenkins controller. An init check requires
restored configuration, keys, admin profile, startup hook and verified-transfer
marker, preventing startup on an empty migration volume. Migration JCasC retains
local authentication/admin authorization but imports no Job DSL, passwords,
agents or clouds. The default overlay still supports fresh foundation bootstrap;
do not apply it over the migrated controller as routine reconciliation.

The original extraction included the archive root entry against a root-owned
PVC mount root and returned an error after copying all files. The helper now
excludes that entry. Independent comparison found all 6,372 files present with
matching hashes and no extras. The verified-copy continuation rechecked the
foundation rollback archive and all target file hashes before startup; nothing
was overwritten to bypass a check.

The initial credential inspection incorrectly selected a GitHub App password
getter, which attempts installation-token retrieval. The egress hold blocked DNS;
no GitHub API request succeeded or token was created. The verifier was corrected
to read stored App keys only; successful inspection stayed under the egress
hold. No external setting changed and no credential value was printed.

The retained foundation rollback object/procedure is concrete but has not been
executed as a rollback test. Successful state restore does not establish CI,
publication, promotion, failover or old Docker restart readiness. Legacy Docker
containers, volumes, cache and all source backups remain stopped and retained;
missing legacy bind-source paths must be reconstructed before a Docker restart.

## Files and verification

- Extended [staging helper](../../scripts/kubernetes/stage-jenkins-home.py) to
  accept consistent stopped-source input only with the private current admin.
- Added [transfer/continuation helper](../../scripts/kubernetes/restore-jenkins-state.py)
  and [runtime verifier](../../scripts/kubernetes/verify-jenkins-migration.py).
- Added the [held overlay](../../kubernetes/platform/nonprod/jenkins/held/kustomization.yaml)
  while retaining the foundation under `base/`; no image/plugin upgrade.
- Updated [runbook 17](../../runbooks/17-migrate-jenkins-ci.md) with standalone
  links, fresh-bootstrap boundaries, transfer, acceptance and retained-PVC rollback.

All 24 relevant fixture tests passed: 12 staging, three transfer, three runtime
verification, four online-backup and two legacy-stop tests. Coverage includes
source/admin preservation and rejection conditions,
existing-PVC refusal, file-integrity failure preventing startup, secret-safe
success/error output and rejection of an altered admin password hash. Existing
backup/stop checks remain relevant. Live acceptance confirms stored credential
inspection succeeds while external egress remains blocked.

After restoration the Jenkins Pod was Ready without restarts; an observed sample
was 17m CPU/404Mi memory within existing 1 CPU/768Mi limits. This is an idle
snapshot, not CI capacity testing. All five application/root Argo CD Applications
remain Synced/Healthy. No application files, GitHub resources, GHCR images,
credential values, PROD resources, NAT or VM lifecycle were changed. No push.

Next: migrate bounded CI/DinD and separate publisher infrastructure with fresh
cache, then gradual inert smoke/CI activation as reviewed. Pipeline/repository
target changes and legacy promotion activation remain deferred; Phase 9 is open.
