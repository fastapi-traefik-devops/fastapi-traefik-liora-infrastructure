# Phase 9 — Target-state CI/CD: implementation log and test report

Status: **target state reached on 2026-10-25**. Pull requests and the nightly run use the full
gate set, main deploys to STAGE automatically with an acceptance receipt, DEV is deployed
manually, and PROD is released by version tag through a reviewed infrastructure pull request.
The first PROD release `v1.0.0`, a second release `v1.0.1` and a rollback to `v1.0.0` were
performed live. Owner: Tatiana Zainullina (CI/Jenkins).

How the pipelines work and how to operate them: [CI/CD guide](../CI_CD.md), application
`ci/README.md` (gate profiles) and `ci/RELEASE.md` (release and rollback). Current summary and
open items: [Implementation plan, Phase 9](IMPLEMENTATION_PLAN.md#phase-9--move-promotion-and-ci-ownership).

All times are UTC. Repositories: application `fastapi-traefik-liora-application` (app),
infrastructure `fastapi-traefik-liora-infrastructure` (infra).

## Implementation log

| Date | Change | Pull requests |
| --- | --- | --- |
| 2026-10-23 | Minimal live cycle on K3s: main → CI → publication → STAGE, verified manually | app #62, #63 ([live cycle](PHASE9_LIVE_CYCLE.md)) |
| 2026-10-24 | Automatic STAGE acceptance: read-only `stage-observer` agent, receipt `overlays/stage/acceptance.json`, one `liora-stage-promotion` lock through acceptance | app #65; infra #1, #3, #4, #6 |
| 2026-10-24 | Promotion validator: strict pinned CRD schemas (CNPG `Cluster`, Barman Cloud `ObjectStore`, cert-manager `Certificate`), kubeconform fail-closed | app #67, #68 |
| 2026-10-24 | Gate profiles restored: `full` (18 gates + `gitops`) for nightly, `release` for main; CVE triage of the first `full` run (`uv.lock`, nginx `1.30.6`) | app #69 |
| 2026-10-24 | Manual DEV deployment: job `dev-build` (`BRANCH` parameter), `ACTION=dev`, direct commit to `overlays/dev/`; checkout of the selected branch only | app #70, #71, #73; infra #10 |
| 2026-10-25 | Manual PROD release: `ACTION=prod`, `vX.Y.Z` tag of a STAGE-accepted SHA, review branch `promotion/prod/<tag>`, rollback by re-release (`-redeploy-<infra sha>` branch, `unchanged` when already live); publisher bundle `jenkins-publisher-ci-9c2084ceb24c` | app #76; infra #12 |
| 2026-10-25 | Pull requests return to `full`; the temporary `pr` profile is removed | app #77 |
| 2026-10-25 | User guide and setup from zero | infra `docs/CI_CD.md` |

Final pipeline matrix:

| Trigger | Jenkins job | Profile | Publishes | Target |
| --- | --- | --- | --- | --- |
| Pull request | `app-ci/PR-<n>` | `full` | no | — |
| Nightly (`H 2 * * *`) | `app-ci/main` | `full` | no | — |
| Commit on main (`pollSCM H/2`) | `app-ci/main` → `trusted/publish` | `release` | yes | STAGE, automatic, with acceptance |
| Manual | `dev-build` → `trusted/publish` | `dev` = `release` | yes | DEV, direct commit |
| Manual | `trusted/publish`, `ACTION=prod` | none, reuses the accepted pair | no | PROD, reviewed infra PR |

## Test report

The test change was Dependabot app PR #58 (`astral-sh/uv` 0.13.1 → 0.13.5 in the backend image):
a real dependency update that changes the backend image and leaves the frontend unchanged.
The test plan followed the local manual test plan, sections 2–6.

### 1. Pull request — `full` profile

| Check | Result |
| --- | --- |
| `app-ci/PR-58`, profile `full`: 18 gates + `gitops`, including `backend-integration` and `frontend-tests` (e2e) | passed, 18:11:36 → 18:43:24 (~32 min) |
| GitHub status `continuous-integration/jenkins/pr-merge` | success |

### 2. Manual DEV deployment

| Check | Result |
| --- | --- |
| `dev-build`, `BRANCH` = PR #58 branch, head `9bd6f60` | passed; `trusted/publish` `ACTION=dev` started automatically |
| Infra commit | `698889e` at 18:58:21, exactly 2 files: `overlays/dev/kustomization.yaml`, `promotion.json` |
| Argo `app-dev` | Synced/Healthy on `698889e` |
| Running images | backend `sha256:160875c4…5b17c` (new), frontend `sha256:3ac9b636…9368` (unchanged) |
| `https://dev.liora.aprt.info` | HTTP 200, health check `true` |

The frontend digest did not change because the frontend source did not change: builds are
reproducible, so DEV and STAGE run byte-identical images for the same source.

### 3. Main → STAGE with automatic acceptance

| Check | Result |
| --- | --- |
| PR #58 merged | 19:04:07, merge commit `2a6e05a` |
| `app-ci/main`, profile `release` (started by SCM polling) | success at 19:14:28 |
| STAGE promotion commit | `289f323` at 19:18:07 |
| Acceptance receipt commit | `004b90e` at 19:21:30, `"status": "accepted"`; `argo`, `running_images`, `url` = `true` |
| Merge to accepted STAGE | ~17 min, no manual action |

### 4. First PROD release `v1.0.0`

Candidate: `48b443fc69f2bdb17d52d95526e84811ab13b6d0` (merge of app PR #77, STAGE accepted
earlier the same day). Images: backend `sha256:640a26a7…`, frontend `sha256:3ac9b636…`.

| Step | Time | Result |
| --- | --- | --- |
| Tag `v1.0.0`, `trusted/publish` `ACTION=prod` | — | passed; acceptance receipt for the SHA and pair found |
| Review branch `promotion/prod/v1.0.0` | 19:54:31 | commit `e8c303f`, only `overlays/prod/kustomization.yaml` and `promotion.json` |
| Infra PR #15 merged | 19:56:33 | merge `da4704a` |
| Argo PROD `app-prod` synced | 20:03:23 | Synced/Healthy; no manual refresh |
| Pods | 20:03:24–20:03:45 | 2 backend + 2 frontend Ready on the released digests; prestart Job completed |
| `https://liora.aprt.info` | 20:03:45 | HTTP 200, health check `true` |

Merge to working PROD: ~7 min (Argo CD polling interval, no webhook).

### 5. Second release `v1.0.1`

Candidate: `2a6e05a…` (PR #58, accepted on STAGE in step 3), backend `sha256:160875c4…`.

| Step | Time | Result |
| --- | --- | --- |
| Review branch `promotion/prod/v1.0.1` | 20:09:36 | commit `120abb7` |
| Infra PR #16 merged | 20:11:54 | merge `2026117` |
| Argo sync finished | 20:15:19 | PROD runs `v1.0.1` |

### 6. Rollback drill `v1.0.1` → `v1.0.0`

| Step | Time | Result |
| --- | --- | --- |
| Migration check `git diff v1.0.0 v1.0.1 -- backend/app/alembic/versions` | — | empty, rollback safe |
| `trusted/publish` `ACTION=prod`, `APP_SHA` = `v1.0.0` SHA, `RELEASE_TAG=v1.0.0` | 20:18:36 | redeploy branch `promotion/prod/v1.0.0-redeploy-2026117`, commit `6e097f4` |
| Infra PR #17 merged | 20:19:44 | merge `a32e4db` |
| Argo sync finished | 20:25:48 | PROD back on `48b443f` digests |
| Pods Ready, site 200, health `true` | 20:26:10 | previous ReplicaSet `backend-7b8df46b5b` reused |

Rollback from start of the Jenkins job to working site: ~8 min. Nothing was rebuilt; the
pair accepted for `v1.0.0` was reused from GHCR.

### 7. Nightly `full` run on main

| Check | Result |
| --- | --- |
| `app-ci/main` #24, cause `TimerTriggerCause` (`H 2 * * *`), description «Profile full (nightly)» | SUCCESS, 2026-10-25 02:15:15 → ~02:41 (26 min) |
| Commit | `cce22bf5728ffb9b256d755206e95da0e6559b54` (main at that time) |
| Stages | all 18 gates (`config`, `secrets`, 8 backend, 8 frontend incl. `backend-integration` and `frontend-tests`) and `gitops`; JUnit results without failures; Playwright 41 passed |
| Publication | none: no `trusted/publish` build between 2026-10-24 19:29 and 2026-10-25 15:29 |

The build history also keeps the nightly runs of the previous Jenkins host (#3, #5 on
2026-10-19/20, `full`, SUCCESS); #7 and #11 (2026-10-21/22) failed before the profile
restoration and the CVE triage of app PR #69.

### 8. Reproducible observer installation

Goal: a new or restored controller gets the STAGE observer from Git and the controller alone,
without copying anything from the running cluster. Changes (infrastructure branch
`ci/observer-reproducible-install`):

- The observer bundle has its own pin `OBSERVER_SOURCE_COMMIT = 8b584055a83c…` (merge of app
  PR #65) in `prepare-jenkins-publisher-source.py`; the publisher stays on `9c2084ceb24c…`.
  `ci/stage_acceptance.py` is identical in both commits.
- New installer `scripts/kubernetes/deploy-jenkins-observer.py` (runbook 27, section 3):
  requires the execution hold, checks the manifest pin against the generated bundle,
  installs the immutable bundle before the Deployment, creates
  `jenkins-acceptance/stage-observer-connection` (key `agent-secret`) from the controller's
  `stage-observer` inbound identity, waits for the node and verifies the mounted helper hash.
  It refuses to replace a different bundle or Secret and never reuses a publisher token.

| Check | Result |
| --- | --- |
| Generated observer bundle vs live ConfigMap `jenkins-acceptance-ci-8b584055a83c` | identical name and `data_sha256` `d0dad33b…f911fe` |
| Generated publisher bundle vs live `jenkins-publisher-ci-9c2084ceb24c` | identical `data_sha256` `47402c0c…30009b` |
| Live Secret `stage-observer-connection` format | `Opaque`, single key `agent-secret`, as created by the installer |
| `acceptance/` overlay render | OK |
| Unit tests: `test-deploy-jenkins-observer.py` (6), `test-jenkins-publisher-source.py` (8, incl. manifest pin guard), `test-deploy-jenkins-agents.py` (6) | all passed |

The installer was not run against the live controller on purpose: it requires the execution
hold, and the running observer already uses the same bundle and Secret format. The end-to-end
run belongs to the planned controller restore checkpoint ([runbook 23](../../runbooks/23-restore-jenkins-controller.md)).

### Summary

| Area | Result |
| --- | --- |
| PR gate (`full`) | passed |
| DEV manual deployment | passed |
| STAGE automatic deployment and acceptance | passed |
| PROD release by tag through reviewed PR | passed (`v1.0.0`, `v1.0.1`) |
| PROD rollback by re-release | passed, ~8 min |
| Nightly `full` run | passed (#24) |
| Observer bundle reproducible from Git | passed (hash equal to live) |

## Observations and open items

- Not yet tested: re-release of a version
  that PROD already runs (expected `unchanged`), PROD refusal of a SHA without acceptance, a live
  failed-acceptance drill (requires disabling Argo auto-sync for `app-stage`), a controller
  restart.
- PROD deploy time is dominated by Argo CD polling (about 3–7 min after the merge).
- `/api/v1/utils/health-check/` returns `true` without a database, so neither STAGE acceptance
  nor the PROD check proves database connectivity (Phase 9 item 8).
- The startup quiet-mode hook still needs *Cancel Shutdown* after every controller restart.
- Cluster notes for the infrastructure owner: a stale Pod `backend-59b9bb8fdf-tgmnw`
  (`ContainerStatusUnknown`) remained in `app-prod`; DEV `liora-db-1` showed 3 restarts.
- Removal of the obsolete application paths is prepared in app PR #78
  ([cleanup report](APPLICATION_REPOSITORY_CLEANUP.md)) and not merged yet.
