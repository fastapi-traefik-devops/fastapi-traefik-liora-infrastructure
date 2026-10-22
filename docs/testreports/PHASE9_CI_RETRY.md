# Phase 9 — Docker MTU correction and second CI attempt

Date: 2026-10-22. Status: **functional CI accepted; all jobs/publication held**.
The operator's `continue` authorized the correction and one further manual
CI-only attempt described in [the first attempt report](PHASE9_MANUAL_CI.md).
Publication, promotion, polling, schedules, indexing and scans remain held.

## Applied changes and preflight

- Infrastructure `3d0873f`: set DinD default bridge MTU to 1450 and new
  user-defined bridge MTU defaults to 1450, matching the pod interface.
  Only the `host-ci` Docker arguments were patched live. The controller
  and publisher Deployments, policies, resource limits and application workloads
  were unchanged.
- The CI worker rolled out successfully. Work/cache PVC identities were
  preserved. Bounded HTTPS probes inside both bridge types downloaded the same
  528432-byte Alpine package index; both container interfaces reported MTU 1450.
  The temporary probe containers/network were removed before application CI.
- Infrastructure `ece9ddc`: extend the one-shot helper with an explicit previous
  receipt and sequential build number. Six focused helper tests passed. The
  Kustomize render and proposed daemon arguments were verified too.
- Application source remains `cb08cdae2687f3b197a65e994699bd29640a3e07`:
  the previously committed reporting fix, functional migration profile and
  `--no-audit` installs. No further application source changes or Git push.
- Jenkins validated the new definition. A verified local Git bundle supplied
  that exact commit; only the disabled manual job definition was updated.
  The first attempt's receipt, request guard and build record were preserved.

## Attempt #2

Exactly one request was issued for `migration-ci #2`. Its exclusive request
boundary and new receipt are in
`.local-work/private/phase9/manual-ci2-20261022/`; the previous directory remains
intact. All imported jobs are disabled. The helper restores the manual-job hold
and quiet mode after completion or failure and does not request a third attempt.

[Jenkins build #2](http://192.168.77.16:8085/job/migration-ci/2/) finished
**SUCCESS** in **27m 7.3s**. All **13 functional gates** passed, including both
runtime-image builds and both nonroot/health smoke checks. The previously
stalled Alpine package step completed in **4.7 seconds** after MTU alignment.
No resource increase or backend/frontend build-logic change was required.

| Application test suite | Passed | Failed/errors/skipped |
| --- | ---: | ---: |
| Backend unit | 2 | 0 |
| Backend integration | 53 | 0 |
| Playwright browser | 41 | 0 |
| Total | **96** | **0** |

Jenkins JUnit reporting confirms the same totals. The archive contains the
three test XML files, `backend-coverage.xml` and native `migration-result.json`.
That JSON names the exact source SHA, all 13 completed gates, no incomplete
gates, seven explicitly deferred checks and `publishable: false`. The reporting
fix is now verified in actual Jenkins execution. No release `gates.json` or
image tarball was created.

Final preservation and hold checks passed:

- All 29 Pipeline jobs disabled with no triggers; empty queue, no running builds,
  zero controller executors and quiet mode restored.
- Imported item configuration and all three persisted user configuration hashes
  match the baseline, preserving the current administrator login.
- The original 28 jobs retain 139 historical build records. The manual job now
  retains #1 ABORTED and #2 SUCCESS: 141 records in total. All four archived XML
  files from #1 match their previously saved SHA-256 values.
- The controller and CI containers have zero restarts. Docker has no remaining
  test containers or `phase1/*` tags, only its three default networks, and the
  workspace is deleted. Work/cache PVC identities remain unchanged.
- All five Argo CD applications remain Synced/Healthy. Tests used disposable
  Docker PostgreSQL data; no K3s application database was modified or reseeded.
- No scan, publication, promotion, application deployment or Git push was performed.

Twenty-second container samples observed peaks of 143Mi for the agent and
468Mi for the daemon. These are sampled container observations, not full
aggregate workload peaks or capacity/failover acceptance. Some pinned images
needed re-pulling; existing cache/cleanup behavior was preserved. Resource
limits were unchanged.

## Scope remaining

This is functional CI acceptance only. The existing full/release profiles and
publisher requirements are retained. Deferred scans, GitOps validation and
attestation must not be reported as passed. No publisher-eligible image archives
or `gates.json` are produced. Tests use disposable Docker PostgreSQL data; the
current Jenkins administrator login and K3s PostgreSQL data remain authoritative.

Phase 9 remains open for separate review of publication/promotion across the
application and infrastructure repositories. Do not activate those jobs or their
legacy direct STAGE push as part of this checkpoint.
