# Phase 9 — Existing pipeline review and CI-only proposal

Date: 2026-10-22. Status: **review complete; CI-only proposal approved; first attempt recorded**.

The operator subsequently agreed to the proposal below. The original review
records the pre-change baseline; current execution/results belong in
[the manual CI report](PHASE9_MANUAL_CI.md).
At the time of this read-only review, no pipeline source, Jenkins job/
configuration, controller policy, credentials or application data was changed. No build, indexing, publication, promotion or scan
was started. Only this documentation and private review artifacts were written.

## Sources and current state

Infrastructure baseline: `e1f65ad5505d2b65b49b589fdd4ac2544c70a415`.
The read-only application checkout and publisher bundle are pinned to
`b98a22e48527c256193ed65c10307eb574b27ab6`.

Anonymous Git/GitHub reads found application `main` at
`13aa29eb27abac01e9638cdf45f1414a4c3002a1`, four commits ahead. The comparison
contains repository-rename changes and fail-fast handling for rejected promotion
pushes. `Jenkinsfile`, `Jenkinsfile.promote`, `ci/phase1.py`, the application
Dockerfiles and image locks are unchanged between these revisions. The newer
`infra/jenkins-host/jobs.groovy`, `ci/promote.py` and `ci/publish.sh` already name
the application repository. Do not redo that upstream rename or assume the
older local checkout represents current GitHub `main`. Neither checkout nor
remote-tracking references were updated during this review.
The [upstream comparison](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/compare/b98a22e48527c256193ed65c10307eb574b27ab6...13aa29eb27abac01e9638cdf45f1414a4c3002a1)
records the exact reviewed difference.

Live, read-only Jenkins inspection found:

| Item | Current state |
| --- | --- |
| `app-ci` | Disabled multibranch project; old repository name; no indexing trigger |
| `app-ci/main` and 25 `app-ci/PR-*` jobs | Disabled SCM-bound Pipeline jobs; script path `Jenkinsfile`; no triggers; resume blocked |
| `host-smoke` | Disabled inline Docker smoke, not application CI; no publication logic |
| `trusted/publish` | Disabled inline publisher, parameter `CI_BUILD`; no triggers; resume blocked |
| `trusted` | Plain credential-bearing folder, retained |
| Controller | Quiet; zero executors, queue items and running builds; 139 build records retained |
| Agents | `host-ci` and `registry-publisher` online, one executor each |

There are 30 configured items and 28 Pipeline jobs. The live publisher definition
matches `Jenkinsfile.promote` exactly: SHA-256
`b45fa648504b2f1d4565d742e07aec0669dba39bfdb165a153542b0f6856709f`.
The source Jenkinsfile hash is
`a5c062f7e186538e255bcedd0bafbdf78361ce59354743505ccbf3217b9dbc07`.
The multibranch parent still names `fastapi-traefik-datascientest-project`;
persisted child metadata mixes old Git URLs with newer application browser URLs.

Private evidence is under
`.local-work/private/phase9/pipeline-review-20261022T150326Z/`, directory 0700,
files 0600. It contains selected job metadata, inline definitions, runtime
hold/trigger inspection and the GitHub comparison. Credential values and raw
credential-bearing XML were not printed or added to Git. The current admin
password authenticated the read-only review; no login configuration changed.

## Findings and minimum adaptation

| Finding | Minimum response |
| --- | --- |
| Manual `main` builds select `release`, set `PUBLISH=true`, and schedule `/trusted/publish` | Do not enable the existing main job for the first CI-only checkpoint |
| Running the existing Jenkinsfile installs its nightly cron | A manual click is insufficient to keep schedules disabled; use a definition with no triggers |
| Both existing profiles invoke security scans | Add an explicit functional-only migration profile; retain the original profiles for later review |
| `attest` requires security reports and publishable image archives; `registry.py` requires the release gates | Skip attestation for this checkpoint; do not weaken `RELEASE_GATES`, fabricate PASS results or produce publisher-eligible evidence |
| `npm ci` enables auditing by default ([npm documentation](https://docs.npmjs.com/cli/v11/commands/npm-ci/#audit)) | Add `--no-audit` to frontend dependency installation and the Dockerfile's install command; explicit future `npm audit` remains separate |
| The `gitops` step validates application-owned legacy deployment/kind/monitoring paths | Defer that step for this application-only checkpoint; later validate the actual infrastructure overlays in the infrastructure repository |
| The config validator and CI image lock still use `infra/jenkins-host/` in the application source | Keep those retained source files for the first build; their checks are not K3s platform validation. Adapt ownership/paths before later cleanup |
| Controller egress is denied, including DNS/GitHub | Use an administrator-installed inline manual definition and agent-side public Git checkout; leave the controller hold policy unchanged for this checkpoint |
| Publisher helpers are immutable and pinned to `b98a22e` | Leave the disabled publisher and bundle unchanged now; update reviewed source/provenance together before later activation |
| Promotion still assumes application code and overlays share one repository | Separate application revision/tag checks from infrastructure overlay writes; a repository-name substitution alone is incorrect |

K3s worker plumbing already matches the pipeline: preserved labels, shared
absolute CI/DinD work path, Docker TLS endpoint, publisher helper path and
credential IDs. No agent rename, new image build, dependency upgrade, credential
rotation or application Dockerfile redesign is needed for migration. The small
`--no-audit` install-option change is solely to honor the scan deferral.

## Proposed next checkpoint — one manual CI-only build

**Recommended: add a separate `migration-ci` job and leave every imported job
disabled.** Its reviewed Pipeline definition would live in the application
repository as `Jenkinsfile.migration` and be installed inline from an exact Git
object by an administrator/operator helper. It would not load the ordinary
`Jenkinsfile`, run Job DSL, index branches, report GitHub statuses or bind write
credentials. The source repository is publicly readable, so an agent-side
checkout does not need a copied App credential or controller GitHub access.

The alternative is adapting/enabling `app-ci/main`, which also requires handling
the parent project, stored SCM metadata, indexing/build strategies, declarative
cron and controller GitHub access. That changes more of the restored setup and
is unnecessary for a single initial CI build. Preserve its history and settings
until the later multibranch activation review.

Approved application-owned changes (original proposal):

| File | Proposed change |
| --- | --- |
| `Jenkinsfile.migration` (new) | Manual-only `host-ci` orchestration; exact approved source SHA; serial functional stages; original report/archive/cleanup behavior; no triggers, publisher or deploy stages |
| `ci/phase1.py` | Add a `migration` profile composed of existing functional steps; append `--no-audit` to frontend `npm ci`; leave existing step implementations, normal profiles and attestation requirements otherwise intact |
| `frontend/Dockerfile` | Change only `RUN npm ci` to `RUN npm ci --no-audit`; retain image pins, stages and build behavior |
| `ci/test_phase1.py` | Check the migration step selection and that existing full/release requirements remain unchanged; no real scanner execution |
| `ci/README.md` | Document manual-only use, deferred checks and non-publishable result |

The proposed 13 steps reuse the current order and implementations:

1. `config`
2. `backend-dependencies`
3. `backend-lint`
4. `backend-unit`
5. `backend-integration`
6. `frontend-dependencies`
7. `frontend-lint`
8. `frontend-build`
9. `frontend-tests`
10. `backend-image`
11. `frontend-image`
12. `backend-image-smoke`
13. `frontend-image-smoke`

No Gitleaks, pip-audit, npm audit or Trivy invocation; no `gitops`, `attest`,
publisher scheduling, image push, promotion or deployment. Preserve separate
full/release behavior as inactive code; skipped checks must be reported as
deferred, not passed. Archive JUnit/coverage and a migration-only source/result
record. Do not create release `gates.json` or publishable image tarballs.

Approved infrastructure/operator changes (original proposal):

- Add a small guarded operator helper to install the reviewed job **disabled**,
  recording the source SHA/definition hash and baseline controller/job state.
  Do not re-enable the legacy startup Job DSL or copy publisher credentials.
- Use the reviewed current application source as the base for a new commit
  containing the agreed changes. A build of unchanged `b98a22e` or `13aa29e`
  cannot exercise the proposed new profile. Make that exact committed source
  available through an agreed remote ref, or a Git bundle transferred to the CI
  work volume when keeping changes local. No Git push is authorized by this
  review. Do not update the existing publisher bundle merely to run CI.
- After agreement and verification of an empty queue, enable only `migration-ci`,
  temporarily leave quiet mode, and manually request **one** build. Keep all
  existing jobs, multibranch scans, polling and schedules disabled.
- Run on `host-ci` with the existing image, Docker daemon and resource limits.
  All Git operations for the build run on that agent. No controller egress
  policy change or publishing credential is required.
- Reuse the existing disposable Docker PostgreSQL/Mailpit/test network, generated
  CI-only credentials and cleanup. Never point tests at K3s PostgreSQL Services,
  mount their data volumes, or seed/restore their contents.
- After the build finishes or fails, disable the manual job again and restore
  controller quiet mode. Report its exact SHA/build number, actual stage/test
  outcomes, archived evidence, resource observations and explicit deferred checks.
  No automatic retry, publication or next activation checkpoint.

Current E2E container memory limits sum to 3Gi before daemon overhead (Playwright
2Gi, backend 384Mi, Mailpit 384Mi, PostgreSQL 256Mi), while DinD is limited to
2560Mi. Limits are not actual usage; the tiny earlier Docker smoke did not prove
this workload fits. Keep the agreed limits initially and measure the one build;
an OOM/failure must be reported before proposing a targeted adjustment. Retain
the existing 90-minute pipeline timeout initially.

## Later changes — separate review before publication/promotion

- Apply the already-merged application repository rename to the restored
  multibranch configuration and its branch SCM metadata deliberately. Preserve
  historical PR jobs/builds; do not scan or regenerate jobs just to update URLs.
- Review the regular Jenkinsfile's release selection, nightly trigger and
  publication handoff before enabling it. Its old `deploy/overlays/` loop filter
  will no longer express infrastructure-only changes after the split.
- Preserve `registry.py`'s successful-source-build check, exact SHA, archive
  integrity checks, write-once tags, digest verification, locks and publisher
  credential scope. The current publisher cannot accept this CI-only result;
  any later change to release evidence requires its own explicit review.
- Adapt `Jenkinsfile.promote` and its helpers so publication and a reviewed
  infrastructure PR replace the unconditional legacy STAGE push. Keep this
  entire job disabled until that implementation is reviewed.
- Give promotion tooling distinct application and infrastructure repositories:
  application ancestry/release-tag checks run against application Git history;
  digest updates and promotion records go under
  `kubernetes/apps/liora/overlays/{dev,stage,prod}/` in infrastructure Git.
  Never test an application SHA for ancestry in infrastructure `main` or push
  overlays to application `main`. Validate the actual infrastructure manifests.
- Update the trusted helper pin/immutable ConfigMap only with the reviewed
  publisher change. Keep build/test implementation in the application repository
  and cluster/GitOps ownership in infrastructure. Retirement of legacy source
  paths and broader promotion activation remain later work.

Current admin credentials and K3s PostgreSQL data remain unchanged. Vulnerability
remediation and further security scans remain deferred. Operator agreement was
received before editing sources or enabling the one manual job.
