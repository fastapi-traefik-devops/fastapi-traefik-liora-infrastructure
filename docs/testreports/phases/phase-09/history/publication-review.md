# Phase 9 — Publisher and repository-split review

> Superseded decision, 2026-10-22: the operator approved local implementation
> with automatic direct STAGE commits (no PR/approval), manual DEV/PROD and
> automatic STAGE acceptance as the PROD gate. Earlier STAGE-PR proposals below
> are historical. The latest priority uses a minimal initial STAGE cycle with
> manual first-deployment checks; observer/receipts are deferred, PROD blocked. See [current implementation](publication-implementation.md).

Date: 2026-10-22. Status at that review: **review complete; proposal then awaiting agreement**.
Current agreement/priority is recorded in the supersession note above.
Only documentation and private review receipts were written. No Pipeline source,
job definition, publisher bundle, credential, network policy or cluster resource
was changed. No token was minted, job activated, image published, Git reference
pushed, PR created or application deployed. Scans remain deferred.

## Verified baseline

- Infrastructure checkout `5000eb8`; application checkout
  `cb08cdae2687f3b197a65e994699bd29640a3e07`, both clean before review.
- Anonymous `ls-remote` reads found application GitHub `main` at
  `13aa29eb27abac01e9638cdf45f1414a4c3002a1` and infrastructure GitHub `main` at
  `11123a58e22d7834ae993f6861e9af8a893b0803`. At review time, the local checkouts
  contained two and eleven additional commits respectively. These reads did not
  fetch objects or update remote-tracking refs; no push is authorized by this review.
- All 29 Jenkins Pipeline jobs disabled, controller quiet, queue/running counts
  zero. The accepted [functional build #2](ci-retry.md) has no image
  tarballs or release attestation; its native result says `publishable: false`.
  Cleanup removed its local image tags. It cannot be published retrospectively.
- The trusted helper ConfigMap remains pinned to application `b98a22e`; the
  publisher definition and regular main Pipeline retain their legacy behavior.
- Runtime type inspection confirmed that `github-ci-app` and `gitops-app` are
  GitHub App credentials compatible with the existing username/password binding.
  `ghcr-write` is a username/password credential in `trusted`. No publishing/App
  credential values or token getters were accessed. This confirms binding compatibility, not current remote
  authentication or permission validity; App grants were checked earlier.
- The controller's `jenkins-migration-hold` policy denies all egress. The
  publisher already has public HTTP/HTTPS and DNS egress. Its existing image
  includes Python, Git, crane, Kustomize and kubeconform: no image rebuild,
  dependency upgrade or additional scan is needed for this proposal.
- All three actual application overlays render, 14 resources each. Both
  application images are digest-pinned in every environment. DEV/STAGE have
  imported `promotion.json` files; PROD currently has no such record. Do not
  manufacture a historical PROD release record or treat imported records as
  proof of a newly reviewed K3s release.

Private receipts: `.local-work/private/phase9/publisher-review-20261022/`.
They contain held-state hashes, credential types, policy metadata and rendered
image summaries; no credential values.

## Findings and minimum changes

| Existing behavior | Required adaptation |
| --- | --- |
| `registry.py` requires release gates, archive hashes and exact successful-source SHA | Keep these checks for existing modes; build #2 does not satisfy them |
| Security deferral conflicts with invoking the existing release profile/attestation | Propose a separate, explicit functional-artifact mode; never mark deferred scans PASS or silently accept a migration JSON as release evidence |
| `Jenkinsfile.promote` assumes `app-ci/main` plus Git plugin `BuildData` | Allow only reviewed source job identities; manual bundle builds need their exact approved SHA/definition/receipt checked without inventing SCM metadata |
| Publishing automatically calls `promote-stage.sh` and pushes STAGE to application `main` | Separate registry-only activation from PR creation; replace every DEV/STAGE direct-main write with an infrastructure review branch/PR |
| `promote.py` uses one repository for application ancestry, tags, overlay writes and STAGE history | Verify application history/tags in the application repository; edit overlays and read promotion history in infrastructure |
| Overlay and validator paths are `deploy/overlays/` | Use `kubernetes/apps/liora/overlays/{dev,stage,prod}/`; retain narrow field edits and render every real overlay |
| PROD creates a branch and prints a compare URL | Create/reuse an actual reviewed PR; never merge automatically or rebuild release images |
| Current tests use one bare Git remote | Extend fixtures to two independent histories plus mocked PR/registry APIs; retain race, rejection, immutability and idempotency cases |
| Publisher helpers are immutable but older than the reviewed application source | Pin the new reviewed helper commit and job definition together; retain the old bundle for rollback |

## Proposed implementation, not applied

1. **Prepare functional image artifacts explicitly.** Reuse the existing 13
   functional gates and image-build/smoke implementations. Add an opt-in export
   path to the manual CI definition, disabled by default. A fresh approved run
   would save the two tested runtime images before cleanup and record their
   hashes/digests, source SHA and source build identity in a distinct versioned
   candidate manifest, alongside the actual JUnit reports. Record all deferred
   checks explicitly. Keep ordinary migration runs non-publishable and keep the
   existing full/release profiles and attestation requirements unchanged.
2. **Make candidate admission explicit in trusted code.** Add a separately
   selected validator mode to `registry.py`, fixed by the administrator-reviewed
   publisher definition rather than selected by an untrusted artifact. Require
   the complete functional gate set, passing reports, exact successful Jenkins
   build/source SHA and intact archives. Reject missing/tampered evidence and
   unapproved source jobs. Preserve write-once SHA tags, digest verification,
   publication locking and credential isolation. Do not fall back to this mode
   when normal release evidence is missing. This new admission policy requires
   agreement before implementation; it is not authorized merely by build #2.
3. **Keep publication separate from promotion.** Adapt `Jenkinsfile.promote` to
   support an explicitly manual registry-only checkpoint; GitOps PR creation
   stays off initially and does not bind `gitops-app` in that mode. Preserve the
   existing trusted job/history and worker label. CI never receives either
   publishing credential. Continue to execute helpers only from the reviewed
   immutable bundle, never a selected source checkout or copied CI artifact.
4. **Split Git responsibilities in `promote.py`.** Use distinct application and
   infrastructure URLs and data-only workspaces on the publisher. Application
   SHA ancestry, release tags and stale-source checks use application history.
   Infrastructure `main` supplies the target overlays and merged STAGE records.
   Keep exact digest-pair checks and update only the selected overlay's
   `kustomization.yaml` and `promotion.json`. Retain existing record fields;
   add explicit repository/source-build provenance for new promotions.
5. **Create reviewed infrastructure PRs for every environment.** Retain the
   agreed targets: manually selected DEV feature branches, main-to-STAGE PRs
   and release-tag PROD using the STAGE-verified pair without rebuilding.
   DEV trigger/selection UI and automatic activation remain separate reviews. Push only a dedicated
   review branch, create/reuse its PR, and never push to `main`, force-push or
   merge. An existing branch with different contents requires review. Use
   Conventional Commit subjects and explanatory bodies. Check current source
   and target bases again before writing; preserve unrelated concurrent commits.
   GitHub documents [PR creation and its App-token permissions](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request).
6. **Validate the actual infrastructure inputs.** Adapt the trusted rendering
   helper to all three infrastructure overlays and add infrastructure-owned PR
   validation. Require the expected frontend/backend image names, full source
   tags and valid immutable digests; reject placeholder PROD references. Do not
   execute scripts from the data checkout under publishing credentials. Reuse
   Kustomize/kubeconform; do not add vulnerability scanners. Existing imported
   promotion records alone do not establish STAGE test acceptance; PROD review
   must reference the approved STAGE digest pair and its health/test evidence.

Likely application-owned files: `Jenkinsfile.migration`, `Jenkinsfile.promote`,
`ci/phase1.py`, `ci/registry.py`, `ci/promote.py`, `ci/promote-stage.sh`,
`ci/validate.sh`, their focused tests and documentation. Audit the older
`ci/publish.sh` entry point too, so it cannot retain an activatable direct-main
path. Infrastructure-owned changes cover the pinned helper source/operator
receipts, actual-overlay validation and its PR workflow, runbook and plan.
Regular multibranch discovery, nightly scheduling and automatic publisher
handoff stay disabled until a later activation review.

## Activation prerequisites and checkpoints

The proposed next checkpoint is **local implementation and offline tests only**:
two independent bare Git fixtures, mocked GitHub PR/registry responses, artifact
integrity/rejection tests and real overlay renders. It does not activate jobs,
publish images, create PRs, push code or change network policies.

Subsequent live steps need separate agreement:

1. Make the reviewed application/infrastructure commits available on GitHub
   before validating remote ancestry or creating infrastructure PRs. Local-only
   source must not silently bypass the existing main/release checks. No push was
   performed here, and no push is authorized by this document.
2. Run one explicitly approved artifact-producing CI build. Verify and retain
   its archives; never relabel build #2 or rebuild later at PROD promotion.
3. Activate the registry-only publisher once, without creating a GitOps PR or
   deploying. Keep polling/schedules and all unrelated jobs held.
4. Review controller connectivity before GitOps App binding. App installation
   token generation runs on the controller, whose current policy blocks it;
   publisher egress alone is insufficient. The [plugin implementation](https://github.com/jenkinsci/github-branch-source-plugin/blob/master/src/main/java/org/jenkinsci/plugins/github_branch_source/GitHubAppCredentials.java)
   refreshes tokens through GitHub. A minimal proposed change for that later
   checkpoint is controller DNS plus public TCP/443 egress, excluding private
   ranges; native NetworkPolicy does not make this GitHub-only. Do not apply it
   now. Verify repository/owner context for the standalone job and both App
   repository grants before use; no new key or credential ID is proposed.
5. Create one reviewed STAGE PR after explicit approval, then let a human merge
   it before Argo CD deployment. Verify the deployed digests and acceptance
   before any separately reviewed PROD PR. DEV remains optional, not a required
   predecessor to every STAGE build. Rollback remains a reviewed Git change.

Current admin login and K3s PostgreSQL data are preserved. Scans/remediation
remain deferred throughout these proposed migration checks; review does not
activate the original security-scanning profiles or legacy STAGE push.
