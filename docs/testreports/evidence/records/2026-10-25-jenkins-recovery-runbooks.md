# Jenkins recovery and agent procedures — 2026-10-25

## Scope and decisions

Keep controller/worker image digests, plugin pins, labels, credential IDs and
pipeline logic. Adapt existing tools rather than add a parallel tool set.
Runbooks 22 and 23 replace empty placeholders with checklist procedures.
No images were rebuilt. No live Jenkins configuration, jobs, builds, publication,
application deployment, database or PVC was changed during this implementation.

## Implementation

- `stage-jenkins-home.py` preserves the archived administrator by default for
  consistent stopped archives. Explicit administrator substitution remains only
  as an optional historical migration interface. Keys, history and original
  source archives remain intact. Unsafe entries, corrupt archives and incomplete
  archived administrator identities fail closed.
- `restore-jenkins-state.py --backup-only` stops a held controller and uses a
  read-only mounted helper to capture its complete home, Deployment and mounted
  ConfigMaps. The completed manifest records stopped consistency and SHA-256.
  Referenced Kubernetes Secrets remain separate private recovery inputs.
- Restore accepts an unused target PVC name and retains the selected original
  PVC. It requires a stopped-source archive and an execution hold, keeps the
  controller image, creates storage without overwriting an existing claim, and
  verifies transferred files before startup. Resume verifies the source home,
  rollback archive, helper target and transferred files before continuing.
- The agent installer no longer requires a migration receipt or migrated-home
  name. It preserves the actual home/image and configures the existing pinned
  two-worker setup. A mounted startup hook keeps the controller quiet after its
  configuration rollout. Conflicting existing connection Secrets are preserved.
- Runbooks include inputs, locations, hold checks, expected results, interruption
  paths and rollback. CI documentation no longer directs fresh installations to
  static restored-home overlays.

## Local evidence

Executed with `scripts/local-python.sh`:

| Check | Result |
| --- | --- |
| `test-stage-jenkins-home.py` | 12 passed |
| `test-restore-jenkins-state.py` | 6 passed |
| `test-deploy-jenkins-agents.py` | 6 passed |
| Restore and agent CLI `--help` | Passed |
| `kubectl kustomize .../jenkins/held` | Passed; no apply |
| `kubectl kustomize .../jenkins/agents` | Passed; no apply |

Synthetic small archives and mocked Kubernetes I/O exercise preservation,
secret-output canaries, archive rejection, no-overwrite checks, stopped read-only
backup, partial-transfer refusal, and target validation on resume. The agent
configuration test uses real local Kustomize output for fresh and restored home
names and checks the retained image, home, administrator realm and quiet hook.
These checks do not establish runtime restoration or credential decryption.

## Remaining runtime checkpoint

Run only under a separate controlled maintenance window: stopped current-home
backup → new PVC → held restored controller → administrator login, credentials,
history and online-agent checks. Do not run CI, publish images or deploy the
application for this checkpoint. Retain the original PVC and private receipts.
Phase 9 job/bootstrap and automatic acceptance activation remain separate.
