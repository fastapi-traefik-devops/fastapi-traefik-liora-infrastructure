# Phase 9 — One manual functional CI build

Date: 2026-10-22. Status: **one build stopped after a nested-network stall; full CI acceptance pending**. This is the approved
CI-only checkpoint, not completion of Phase 9 or activation of publication.

Follow-up: the operator approved the correction and one further attempt. See
[successful build #2 and final acceptance](PHASE9_CI_RETRY.md). The observations
below retain the original first-attempt outcome.

## Scope and source

The operator approved the [reviewed proposal](PHASE9_PIPELINE_REVIEW.md).
The application checkout was clean and fast-forwarded from `b98a22e` to the
reviewed upstream `13aa29eb27abac01e9638cdf45f1414a4c3002a1`, preserving history.
The approved changes are committed locally as
`c5ee7de03a324f79c86d6f1765f87b4cd6670d14`:

- Separate `Jenkinsfile.migration`, installed inline on a new `migration-ci` job.
- Functional-only `migration` profile reusing 13 existing steps in their order.
- `npm ci --no-audit` for frontend dependencies and image builds.
- Focused profile tests and application CI documentation.

A follow-up source-only report fix is committed locally as
`cb08cdae2687f3b197a65e994699bd29640a3e07`; it was not installed or built.

The normal Jenkinsfile, full/release gate requirements, imported pipelines,
trusted publisher and its pinned helper bundle were retained. No Git push was
performed. A private Git bundle supplies the exact new commit on the CI worker;
all source Git operations execute on `host-ci`. The controller egress policy is
unchanged. Jenkins Declarative Pipeline validation passed before activation.

## Execution controls

[Operator helper](../../scripts/kubernetes/manual-jenkins-ci.py) and
[runbook procedure](../../runbooks/17-migrate-jenkins-ci.md#manual-functional-only-migration-checkpoint)
install the job disabled, verify source/definition hashes and preserve baseline
job configuration/user hashes. An exclusive request boundary is written before
activation. Exactly one manual request is allowed, with no automatic POST retry.
The helper restores quiet mode and disables the job after completion or failure.

Private evidence: `.local-work/private/phase9/manual-ci-20261022/`. Source bundles,
raw console, receipts, controller snapshots and resource observations stay off Git.
Two bulk Kubernetes stdin transfer methods produced truncated files before job
creation. Their hash checks failed safely; partial bundles were retained. The
successful transfer used the existing administrator SSH path, verified the bound
CI local-path PVC and checked SHA-256 before and after copying.

Local checks passed initially: 10 application profile/attestation tests and four operator
helper tests covering duplicate activation, ambiguous POST failure, completed
failed builds and changed imported configuration. Attestation tests use fixtures;
no scanner was executed.

## Result

`migration-ci #1` was requested exactly once and then gracefully stopped by the
operator agent after the backend runtime image stalled at `apk add --no-cache
bash`. Result: **ABORTED**, not a successful full CI build. No automatic retry
was requested. The existing 90-minute timeout was retained; the run was stopped
before that timeout after read-only network diagnostics identified a stall.

Nine of 13 functional gates passed: config, backend dependencies/lint/unit/
integration, frontend dependencies/lint/build/browser tests. Backend runtime
image creation was interrupted; frontend runtime image creation and both image
smokes were not run. The three application test suites reported 2 backend unit,
53 backend integration and 41 browser tests passing: **96 tests, zero failures,
errors or skips**. Duration: **33m 31.5s**. The archive contains the three test XML
files and `backend-coverage.xml`.

The new embedded report writer had an escaping defect: Groovy converted its
newline escape into a newline inside a Python string. That caused a post-action
syntax error, preventing `migration-result.json` generation and Jenkins JUnit
summary publication. The nested `finally` blocks still archived all four XML
files, removed disposable containers/networks and CI image tags, and deleted the
workspace. The absence of native JSON evidence is recorded explicitly; no fake
artifact or PASS attestation was substituted. Jenkins stage metadata, exact SHA
parameters, archived XML and the operator receipt retain the actual result.

The local follow-up fix moves JSON generation into the Python runner's
`migration-report` command, explicitly records incomplete gates, and collects
JUnit independently of result generation. **11** focused profile/report/
attestation tests passed, and Jenkins Declarative validation passed again. That
fixed source has not been installed in Jenkins, built there or pushed.

Final hold verification passed: all **29** Pipeline jobs disabled, no triggers,
empty queue, zero running builds, zero controller executors and quiet mode
restored. The original 28 jobs retain all 139 historical records unchanged;
there are now 140 records including this one aborted attempt. Configuration
hashes for all imported items and the three persisted users match the baseline,
including the current administrator. Controller and CI containers have zero
restarts. Docker has no remaining containers or `phase1/*` tags and only its
three default networks; the aborted builder process ended too. All five Argo CD
applications remain Synced/Healthy. No K3s application database operation was
performed: tests used their disposable Docker PostgreSQL instance exclusively.

Twenty-second metrics samples observed up to 183Mi for the agent and 356Mi for
the daemon container. These are sampled container metrics, not a complete
aggregate workload peak or capacity/HA acceptance. No resource limits changed.
No security scan, image publication, promotion, deployment or Git push occurred.

### Network observations and proposed next change

- Pod `eth0` MTU: **1450**; nested Docker `docker0` MTU: **1500**.
- The same public Alpine index HTTPS fetch succeeded from the pod network and
  timed out inside the active build network with a 20-second probe timeout.
- The stalled `apk` process was waiting on an established TCP/443 socket. The
  retained test services were idle and small; CI containers had zero restarts.
- Docker also logged a BuildKit session health-check failure with
  `only one connection allowed`. Its relationship to the stall is not proven.

A nested-network fault is supported by the probe comparison. MTU mismatch is a
likely contributor; it has **not** been proved the sole cause by a corrective
rollout. No live MTU, daemon argument, network policy, resource or pipeline logic
was changed to make this run pass.

Proposed next checkpoint, requiring operator agreement:

1. Set DinD default bridge MTU to 1450 and new user-defined bridge defaults to
   1450 in the NONPROD CI worker configuration. The proposed daemon arguments are
   `--mtu=1450` and
   `--default-network-opt=bridge=com.docker.network.driver.mtu=1450`.
   Both flags are present in the current pinned daemon's `--help` output.
   Docker documents [bridge MTU](https://docs.docker.com/engine/network/drivers/bridge/)
   and [default network options](https://docs.docker.com/reference/cli/dockerd/#default-network-options).
   The documented [DinD/overlay MTU failure mode](https://docs.gitlab.com/runner/executors/kubernetes/troubleshooting/)
   is consistent with these observations, but is not proof of this run's cause.
2. Roll out only the held CI worker, retaining its work/cache PVCs and current
   controller login. Verify effective MTUs and repeat the bounded HTTPS probe
   from a nested build/test network before requesting another application build.
3. If network checks pass, authorize exactly one further manual CI attempt using
   the report-fix application commit after review. Transfer its exact new bundle
   and install that definition while the job remains held. Use a new explicit
   attempt receipt for build #2; preserve the #1 request boundary and build history. Adapt the helper
   deliberately for that expected build number rather than deleting its guard.

No part of this proposed correction or retry was applied in this checkpoint.

## Deferred work

Security scans/remediation, GitOps validation, release attestation, publication,
promotion and deployment remain deferred. This profile never produces publisher-
eligible `gates.json` or image tarballs. No polling, schedules, indexing or legacy
direct STAGE push is enabled. Preserve current admin login and K3s PostgreSQL data.

After this checkpoint, review any actual failure before requesting another build.
Publication/promotion adaptation for the repository split remains a separate
operator-reviewed checkpoint; do not enable it automatically.
