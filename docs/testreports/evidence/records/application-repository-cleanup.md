# Application repository cleanup plan

Review date: 2026-10-25. Status: approved cleanup implemented on a separate
application branch; PR review and merge remain separate. Live jobs, cluster
resources and private operator data were not changed.

## Review baseline

| Checkout | Local state reviewed |
| --- | --- |
| Application | Clean `dev/sqlalchemy-connection-recovery`, `61b35a0`; local `main` at `cce22bf`; local `origin/main` at `2a6e05a` |
| Infrastructure | Clean `main`, `ac546ea`, before this document update |

Remote-tracking refs are local observations, not a fresh GitHub inventory. The
application working branch contains the SQLAlchemy recovery PR. Do not base
cleanup on that feature branch or include its commits unintentionally. Before
implementation, fetch normally, inspect divergence and open PRs, and create
`chore/remove-legacy-infrastructure` from the approved current application main.
Use the original checkout; do not reset the existing branch or create a repository copy.

## Ownership and migration evidence

The original combined application repository was split: infrastructure moved
**from application to infrastructure**. Application code, tests, image builds
and trusted publication source remain application-owned.

- [Deployment import](../../archive/migration-procedures/application-source-history.md) and [Phase 1](../../phases/phase-01/REPORT.md): selected
  `deploy/` history imported into `kubernetes/apps/liora/`, with provenance in
  `SOURCE_HISTORY.tsv`. Import merge `412e465`, subsequent source update `07a72d2`.
- [Phases 3](../../phases/phase-03/REPORT.md), [4](../../phases/phase-04/REPORT.md) and
  [5](../../phases/phase-05/REPORT.md): DEV, STAGE and PROD deployment acceptance.
- [Phase 8](../../phases/phase-08/REPORT.md): selected `monitoring/` and
  `infra/jenkins-host/` history imported under `kubernetes/platform/upstream/`;
  22 commits, import tip `859a076`, merge `53dcf18`. These upstream files are
  references; current platform manifests are separate.
- [Phase 9 report](../../phases/phase-09/history/report.md) and [current plan](../../IMPLEMENTATION_PLAN.md):
  CI moved to K3s; publisher writes infrastructure overlays, not application
  overlays. The plan records later automatic STAGE acceptance and manual DEV
  work that the older Phase 9 report still lists as pending. Do not use that
  older status paragraph alone as a removal gate. PROD changes exist separately
  and must not be folded into this cleanup.
- [Phase 10](../../phases/phase-10/history/cnpg-installation-2026-10-23.md), [10.2](../../phases/phase-10/history/r2-backup-pitr-2026-10-23.md) and
  [11](../../phases/phase-11/history/certificate-migration-2026-10-24.md): CNPG, R2 and certificates supersede the application
  repository's standalone PostgreSQL and old platform examples.

This is a repository dependency review, not a fresh audit of live Jenkins job
configuration. Check installed job definitions and pinned sources before removing
any migration entrypoint or rebuilding helper bundles.

## Proposed disposition

| Path in application repository | Decision | Required work before removal |
| --- | --- | --- |
| `deploy/base/`, `deploy/overlays/` | Remove obsolete deployment copies | Confirm all current writers/renderers target infrastructure; retain imported history and promotion provenance there |
| `argocd/` | Remove old combined-cluster bootstrap | Update legacy validation caller and documentation; confirm no installed Application/ApplicationSet points here |
| `monitoring/` | Remove old monitoring installation and its local checks | Preserve unique useful material in infrastructure; remove its validation dependency in the same commit |
| `infra/kind/` | Remove retired kind bootstrap and recovery scripts | Archive unique decisions/procedures and update validators; preserve ignored credentials and local recovery material |
| `k8s/` | Remove superseded manifests and encrypted Secret examples | Check historical references and retain any still-required key/ciphertext recovery material privately; do not print values |
| `infra/jenkins-host/` | Split active CI inputs from obsolete host deployment; do not delete wholesale | Relocate the active image lock first; compare current image/tool build sources with infrastructure upstream before retiring other files |
| `Jenkinsfile.migration` | Conditional removal, separate commit | Confirm `migration-ci` is retired and no recovery/setup procedure uses it; update publisher allowlist, functional-only contract, tests and docs together |
| `ci/validate-platform.sh` | Remove or narrow legacy platform validation | `ci/phase1.py` invokes it; keep infrastructure rendering/strict CRD validation intact |
| `ci/validate_phase1.py` | Refactor, retain useful checks | Separate application syntax/pipeline/image checks from obsolete host JCasC/Compose/plugin checks |
| `ci/audit_ci_images.py` | Review with host-build retirement | Its caller is the old bootstrap; preserve infrastructure image-audit capability where needed, without expanding security scope |
| `docs/runbooks/*.md` | Retire old platform operator guides after content review | Move unique history into infrastructure phase reports; replace reusable guidance with current runbook links |
| `docs/template/deployment.md`, `docs/template/development.md`, `ci/README.md`, `ci/ARTIFACTS.md`, `ci/PUBLICATION.md`, root `README.md` | Update, not blanket-delete | Remove Docker-host/kind setup claims and stale deployment paths; keep app development and CI contracts |
| `dev-journal/`, `docs/template/archive/` | Preserve historical material in this cleanup | They are history/template provenance, not current installation instructions; any separate archival cleanup needs an explicit inventory |

Do not delete entire `infra/` or `ci/` directories by pattern.

## Dependencies that block simple deletion

1. `ci/phase1.py` loads `infra/jenkins-host/images.lock.json` on runner
   initialization. `ci/test_phase1.py` copies it into fixtures, and
   `scripts/generate-client.sh` reads its Node image. Move the lock to an
   application-owned CI path and update all three consumers atomically. Preserve
   pinned digests; this is not a tool upgrade. Use the flat path
   `ci/images.lock.json` (implemented), or a path outside `ci/`. Never introduce
   `ci/locks/images.lock.json`: the publisher bundle builder enumerates all
   `ci/` entries and rejects nested names using `[A-Za-z0-9_.-]+`. A flat lock
   is harmless bundle data within the 900 KiB limit. `registry.py` imports
   `phase1`, but reading this lock occurs only during CI initialization.
2. The runner invokes `ci/validate_phase1.py` and `ci/validate-platform.sh`.
   The former reads old JCasC, plugin/image locks and Docker Compose; the latter
   explicitly validates `argocd/`, `infra/kind/` and `monitoring/`. Removing these
   trees without adapting the callers breaks CI even though deployments use K3s.
   `config` runs in all profiles, including `release` and `dev`; breaking
   `validate_phase1.py` therefore also stops main publication and manual DEV.
   `validate-platform.sh` runs only in `gitops` (`full`). It can be deleted
   entirely with those legacy trees: separate `ci/validate.sh` retains strict
   infrastructure-overlay and CRD validation.
3. `.github/dependabot.yml` still includes `/infra/jenkins-host`. Update it when
   those Dockerfiles leave; preserve backend/frontend and Actions updates.
4. Keep `Jenkinsfile`, `Jenkinsfile.dev`, `Jenkinsfile.promote`, `ci/phase1.py`,
   `candidate.py`, `registry.py`, `publish.sh`, `promote.py`, `promote-stage.sh`,
   `publisher-action.sh`, `stage_acceptance.py`, GitOps validators, CRD schemas
   and their tests. They implement current CI/publication/promotion, not obsolete
   deployment copies. `ci/validate.sh` already renders infrastructure paths.
5. Infrastructure `prepare-jenkins-publisher-source.py` reads application `ci/`
   from pinned Git commit `9c2084ceb24cf8b39ee6309f3f648416f47bc719`.
   Deleting old working-tree files does not remove that historical object.
   Do not repin/reinstall bundles as an automatic side effect of cleanup.
6. Infrastructure agent rebuilds use its own upstream host sources through
   `scripts/kubernetes/rebuild-jenkins-agents.sh`. Compare them with application
   sources before retiring the latter: an initial historical import alone does
   not prove that later tool/image changes are preserved.

7. Preserve both historical path-scoped allowlists in `.gitleaks.toml`.
   `secret_scan()` invokes `gitleaks git` across history, where the deleted
   `infra/jenkins-host/plugins.lock.txt`, old SealedSecret files and
   `infra/kind/secrets/...` still exist. These are not dead-path exclusions.
   Keep their existing path-plus-line-format restrictions; do not broaden or
   delete them. The cleanup branch leaves `.gitleaks.toml` unchanged.
8. Concrete migration-entrypoint consumer:
   `scripts/kubernetes/manual-jenkins-ci.py::prepare()` reads the application's
   current HEAD and runs `git show <HEAD>:Jenkinsfile.migration`. Removing the
   file breaks this helper even when the installed job is disabled. Its test is
   `scripts/kubernetes/tests/test-manual-jenkins-ci.py`; `docs/CI_CD.md` also
   documents `migration-ci`. Retirement requires a paired infrastructure PR.

## Proposed cleanup commits and order

All application cleanup commits go on `chore/remove-legacy-infrastructure` and
are reviewed through a PR. No direct main push, merge, deployment or job change
is part of this plan. Each commit requires a concise explanatory body.

1. **`refactor(ci): decouple checks from legacy infrastructure`**
   Move the active image lock to flat `ci/images.lock.json`; adapt runner, fixtures, client generation and
   local validators. Preserve current functional/security gates and real
   infrastructure-overlay validation. Keep legacy trees until this commit passes.
2. **`chore(repo): remove retired deployment and kind sources`**
   Remove approved `deploy/`, `argocd/`, `monitoring/`, `k8s/`, `infra/kind/`
   and obsolete host files after prerequisite comparison. Include affected
   dependency configuration and reference fixes. Preserve historical Gitleaks
   allowlists unchanged. If review is too large, split
   application deployment copies and legacy platform sources into separate commits.
3. **`docs(app): point operations to infrastructure runbooks`**
   Consolidate guides; archive unique execution history under infrastructure
   `docs/testreports/` before removing it from app guides. Necessary link fixes
   belong with deletions; this commit handles the independent narrative cleanup.
   Any infrastructure archival commit uses its own review branch.
4. **`chore(ci): retire the migration-only entrypoint`** — optional later commit.
   Perform only after confirming installed callers no longer need it. Do not
   silently remove the functional candidate contract or enable disabled jobs.
   Prepare a paired infrastructure PR to retire or adapt
   `manual-jenkins-ci.py`, its test and `docs/CI_CD.md`. Update the
   `Jenkinsfile.promote` source-job choices, `PUBLISH_MODE`, compatibility tests
   and documentation together. Because `trusted/publish` is an inline job,
   source changes alone do not activate it: a separately approved Jenkins
   checkpoint must install the reviewed definition and handle script approval.
   Keep this entire retirement outside the present cleanup.

Keep SQLAlchemy PR work, PROD promotion work and other open feature commits out
of the cleanup branch unless they have already merged into the approved base.
Do not rewrite imported history or use history filtering to remove these paths.
After cleanup merges, owners of open branches that edit `phase1.py` or
`test_phase1.py` must update from main and resolve the image-lock path before
rerunning PR checks. Prefer merging main to preserve published history; any
rebase of an existing PR requires its owner's explicit agreement. Do not rebase
SQLAlchemy or PROD branches as an automatic cleanup action.

## Approval and execution checklist

- [x] Owner approved implementation. Conditional migration-entrypoint retirement remains deferred.
- [ ] Refresh application main and inspect open PRs/pins for concurrent changes.
- [ ] Verify current Argo source paths and installed Jenkins entrypoints read-only.
- [ ] Compare unique source/content before deletion; record any retained material.
- [x] Created the separate cleanup branch without resetting existing work.
- [ ] Preserve `.env`, `.ci-private/`, ignored artifacts, keys, credentials,
      Jenkins state and all recovery inputs. Never use `git clean` for this task.
- [ ] Run `python3 -B -m unittest discover -s ci -p 'test_*.py'` and relevant
      syntax/shell checks after each affected commit; fix fixtures rather than
      weakening checks to accommodate deleted input.
- [ ] Verify backend unit and integration selections remain separate; run the
      existing CI selection checks without triggering publication/deployment.
- [ ] Validate infrastructure overlays and the revised CI/platform-validation path
      with existing pinned tools. Check client-generation image resolution.
- [ ] Search executable callers and active documentation for removed paths;
      allow clearly marked historical references only. Validate links/anchors.
- [ ] Review staged diffs, including deletions and absence of private inputs.
- [ ] Push only the approved cleanup branch for PR review; do not merge or deploy.

## Execution results — 2026-10-25

### Branches and commits

Application branch: `chore/remove-legacy-infrastructure`, based on freshly
fetched `origin/main` at `2a6e05a91489b2d9475e25157ab73d8ff9c98d08`.
The existing SQLAlchemy branch remains unchanged at `61b35a0`. No feature
branch was reset, rebased or merged for this cleanup. Current main already
contains later PR work; the cleanup adds only these three commits:

| Commit | Change |
| --- | --- |
| `6d2b01a` | Move unchanged CI image lock to `ci/images.lock.json`; update runner, tests, client generation and application-only validation |
| `5163d5e` | Remove old `deploy/`, `argocd/` and `k8s/`; update deployment/development navigation |
| `5a05832` | Remove old monitoring, kind and Docker-host installation sources, unused legacy validators/audit entrypoint and platform guides; update Dependabot and mark template archive as historical |

Infrastructure documentation branch: `docs/application-cleanup-results`.
The previously prepared cleanup-plan edit was preserved and extended here.

### Read-only ownership checks

- NONPROD `app-dev`, `app-stage` and `liora-root-nonprod` all reference the
  infrastructure repository and current environment/root paths.
- PROD `app-prod` and `liora-root-prod` reference the infrastructure repository.
- Installed `app-ci` uses `Jenkinsfile`; `dev-build` uses `Jenkinsfile.dev`;
  trusted publisher is inline. No job configuration was saved or changed.
- `migration-ci` still exists and is disabled. Its entrypoint and functional
  candidate compatibility remain deliberately intact. Retiring it requires a
  separate caller/recovery review; this is the only deferred cleanup commit.

### Preserved source and operator data

[Historical archive](../../application-legacy-archive/README.md) retains the former
platform guides, deployment procedure and differing Jenkins README, security
notes, Job DSL, App diagnostic script and CI image-audit helper at their
original source paths.
Other retired source remains in application Git history at the baseline SHA.
The archive is historical and must not be executed as current installation code.

All tracked host Dockerfiles, build/install scripts, image/tool/plugin locks
matched the infrastructure upstream copies byte for byte, except the four
explicitly archived differing files. The image lock was moved, not upgraded.
Current Jenkinsfiles, publishing/promotion helpers, strict CRD schemas, tests,
release guide and the migration-only pipeline remain application-owned.
`dev-journal/` and archived template sources remain intact.

Only explicit tracked paths were removed with `git rm`. No `git clean` was
used. Hash comparisons confirmed existing `.env` and `.ci-private/` files were
unchanged. Ignored data inside retired directories was not removed. No Jenkins
state, credentials, recovery inputs, PVCs, databases, image digests, helper pins
or live automation settings were modified.

### Verification results

- CI helper suite: **95 tests passed before deletion and 95 after deletion**.
  Includes unit/integration selection and current publication/promotion fixtures.
- `python3 -B ci/validate_phase1.py`: passed after refactoring and after deletion.
  Application Python/shell syntax, read-only workflows, pipeline restrictions
  and pinned image checks remain active.
- Existing application GitOps validator and kubeconform, using installed tools:
  **DEV 14/14, STAGE 14/14, PROD 14/14 valid; no errors or skipped resources**.
- CI image lock matches the pre-cleanup source exactly. Client generation still
  resolves the same pinned Node image; generation itself was not run.
- No retired installation paths remain in active README, template guides, CI,
  workflow or script references. Historical archives intentionally retain their
  source-context references.
- Changed active document relative links resolve. Infrastructure runbook links
  were checked against local target files. Historical copied links remain in
  their original source context, as stated in the archive index.
- Gitleaks scanned the new archive with redacted output: **no leaks found**.
- Staged patch scope and whitespace checks passed. Added files contain no private
  inputs. Validation output is retained under ignored
  `.local-work/application-cleanup/` in infrastructure.

No full Docker/application test build, Jenkins build, image publication,
deployment or database operation was run. CI helper tests use fixtures and mock
registry operations; their log messages are not actual image publication.

### Publication

Application cleanup branch pushed normally to origin at `5a05832`.
[Open the application PR](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/pull/new/chore/remove-legacy-infrastructure).
No main branch push, merge or deployment was performed.

Infrastructure branch push was attempted normally and rejected with
`Permission to fastapi-traefik-devops/fastapi-traefik-liora-infrastructure.git denied to deploy key`.
The report and archive remain committed locally on
`docs/application-cleanup-results`. No credentials or permissions were changed.
An authorized infrastructure writer must publish that documentation branch.

### Remaining actions

- Review the cleanup branch in an application PR; do not merge automatically.
- Merge/publish the infrastructure archive and report through its documentation
  review branch so historical links resolve on infrastructure main.
- Retire `migration-ci` and its compatibility code only through the separate
  conditional cleanup review. Keep it disabled meanwhile.
- Live CI after a future merge must follow the existing approved pipeline;
  this cleanup does not authorize changing jobs, schedules or helper pins.

## Follow-up dependency review — 2026-10-25

The owner identified three constraints requiring explicit plan wording. Checked
the current source and recorded them above: historical Gitleaks allowlists, flat
publisher-bundle paths and the concrete infrastructure migration-helper caller.
The implemented branch already preserves both allowlists, uses flat
`ci/images.lock.json` and retains `Jenkinsfile.migration` and its publisher
compatibility. No corrective application source change is required for these
three points.

The local branch/ref table near the top is an initial-review snapshot, not a
required current main position. The execution base is the fetched remote SHA
recorded in execution results; always refresh refs before subsequent work.

The differing `check-github-apps.sh` and `jobs.groovy` contain the new application
repository name; upstream retains the old name. Current nonhistorical reference
search found only the upstream historical README mentioning that diagnostic
script. Its corrected tracked source is preserved in the reports archive. No
current runbook or runtime installation was changed to use the old copy. If the
diagnostic is made operational again, promote the corrected source into a
focused infrastructure helper and update its paths and instructions first.

### Additional history-scan evidence

With the unchanged application `.gitleaks.toml` and the gate's redaction and
ignore-comment options, Gitleaks scanned cleanup `HEAD` history explicitly
(`--log-opts=HEAD`): **883 commits, no findings**.

The default all-ref scan of this operator checkout scanned 917 commits and
returned seven `generic-api-key` findings from commit
`0d7d91dfd5fa51edca91b53e3a18389829d43abb`, reachable only from local
`origin/docs/backend-api-evidence`, not from cleanup HEAD. The affected paths
are `docs/backend-api-evidence-2026-10-24/evidence/provenance.json` and four
`evidence/results/*.json` files. Findings have not been classified as real
credentials or false positives. No values are recorded here. This is an
existing separate-branch finding, not a cleanup regression. A full all-ref
scan in a checkout containing that branch currently fails and needs separate
triage; do not suppress findings or delete refs to make the check pass.
Redacted reports and logs remain in ignored `.local-work/application-cleanup/`.
