# Phase 9 — Bounded CI workers and publisher

Status: **workers deployed and verified; application jobs/publication remain held**.
Date: 2026-10-22. Application source remains read-only at
`b98a22e48527c256193ed65c10307eb574b27ab6`.

## Scope and operator decisions

Continue the held state restore with the original `host-ci` and
`registry-publisher` names/labels, one executor each, zero controller executors
and existing pipelines. Preserve the current K3s admin account/password. Keep
imported jobs, scanning, resume and publication disabled pending review.
Recreate Docker cache instead of transferring the legacy cache.

The operator explicitly deferred vulnerability remediation and further scans
for this educational deployment. Before that decision, the recovered controller
passed the High/Critical gate. Rebuilt DinD failed with five instances of
`CVE-2026-111943` in its Go binaries; that result remains a failure. The
[Go advisory](https://pkg.go.dev/vuln/GO-2026-6809) identifies fixed standard
library versions. No Dockerfile/tool-lock change, remediation-specific upgrade,
allowlist, finding suppression or further image scan was performed after the
deferral. The agent is not rescanned.
The retained audit helper is optional and is not called by deployment.

Kind applications held only default installation data, as confirmed by the
operator. Keep current K3s PostgreSQL content; no application data transfer,
replacement or reseeding belongs to this increment.

## Image recovery and provenance

The operator's Docker prune removed stopped legacy containers, local images and
the kind node's anonymous volume. Seven named Jenkins volumes remain; all 14
stopped-source archive size/hash checks passed. K3s homes remain separate from
that cleanup. See [Phase 9 report](PHASE9_REPORT.md) for recovery boundaries.

The exact controller image was recovered from the complete audit export made
before cleanup. Agent/DinD tags were absent from GHCR and had to be rebuilt from
the unchanged imported Dockerfiles/tool locks. Existing APK upgrade/install
steps resolve current packages, so these are new builds with new image IDs.
The isolated BuildKit builder uses 3Gi, 1.5 CPU and one build step at a time.
The cold source build includes the original bundled tools; compiling Trivy
does not mean running a vulnerability scan.

DinD was published as
`ghcr.io/fastapi-traefik-devops/liora-jenkins-dind:phase9-b98a22e-20261022-recovered`
with digest
`sha256:8a1438a15d85154fc53aa500782707780dd0d0ce7f8bc256ac200eb47c2787fc`.
The agent was published as
`ghcr.io/fastapi-traefik-devops/liora-jenkins-agent:phase9-b98a22e-20261022-recovered`
with digest
`sha256:9c4e2acf5ce2637353ccb3c0d00928c8af521a2f4c0effd4f85f9994afb608c6`.
Both pushed digests match the manifest pins. The build wrapper was edited while
running and failed at its final receipt step after both images loaded; independent
image inspection verified their IDs and created that receipt. The saved wrapper
passes shell syntax validation. No image rebuild was needed to recover the receipt.

## Implemented cluster adaptation

The `jenkins/agents` overlay extends the restored `held/` configuration. It
retains the migration PVC, current admin profile, quiet startup hook, disabled
inbound TCP listener and controller egress hold. JCasC adds the two static nodes
without importing Job DSL or declaring a user/password reset.

| Component | Namespace | Request | Limit | Storage |
| --- | --- | --- | --- | --- |
| Controller | `jenkins` | 100m / 512Mi | 1 CPU / 768Mi | Existing migrated home 5Gi |
| CI agent | `jenkins-ci` | 100m / 192Mi | 500m / 384Mi | CI work 5Gi |
| DinD sidecar | `jenkins-ci` | 250m / 1Gi | 1500m / 2560Mi | Fresh cache 20Gi; same CI work path |
| Publisher | `jenkins-publisher` | 100m / 256Mi | 500m / 512Mi | Separate work 5Gi |

CI/DinD share `/home/jenkins/agent` so nested bind mounts use the same absolute
path. Generated Docker TLS client/server/CA inputs remain in that Pod. The
publisher has no Docker certificates/socket and mounts immutable helper source
read-only at `/opt/phase1-ci`. No service-account token or host Docker socket is
mounted into workers. DinD remains privileged as explicitly approved; this is
not a worker-kernel isolation guarantee.

The publisher ConfigMap preserves all 17 `ci/` files from verified Git objects
at the exact source commit, without executing or changing them. Its data hash is
`6bf31a79de4c801b3084683870b6bc9fe8fc55265aa12ff128195d2c549fc243`.
Only kubelet image-pull credentials and per-node Jenkins connection identities
are provisioned to the new namespaces. App/publisher credentials remain in
their restored Jenkins folder scopes.

Basic network policies retain build/publication separation: no worker ingress,
DNS and private controller access, public HTTP(S) egress. There is no DinD
Service. These preserve the approved runtime boundary; no broader security
hardening or scan stage is introduced.

## Runtime acceptance

Private evidence is
`.local-work/private/phase9/agents-20261022T143749Z/` (0700; files 0600): original
controller/configuration, acceptance inputs, desired manifests and pinned source
bundle, deployment receipt, runtime Pod image/status snapshot, Docker smoke
receipt and independent runtime acceptance. Earlier zero-agent acceptance is
retained separately and was not overwritten.

| Check | Result |
| --- | --- |
| API validation | Worker/controller manifests passed server dry-run |
| Controller | Ready on `k3s-1-03`, zero restarts, same image and migrated home |
| CI/DinD | Both containers Ready on `k3s-1-01`, zero restarts |
| Publisher | Ready on `k3s-1-03`, zero restarts |
| New storage | CI work 5Gi, cache 20Gi and publisher work 5Gi Bound |
| Worker images | Runtime repository digests match both published manifest pins |
| Agent connections | Original names/labels, one executor each, both online |
| Publisher helpers | All 17 mounted file hashes match reviewed Git objects |
| Current admin | Password works through API/browser; stored hash unchanged |
| Retained state | 30 items, 139 builds, three persisted users; original encryption/HMAC keys |
| Stored credentials | Both App keys and registry password decrypt; original scopes/IDs |
| Plugins | 84 locks match; 85 loaded including original `locale`; zero failed plugins |
| Execution hold | Quiet, zero controller executors/queue/running builds; jobs/scans/resume disabled |
| Controller outbound hold | Baseline public-IP probe remains blocked |
| Docker smoke | Tiny local build and nested read-only work bind passed; no Jenkins job or application publish |
| Existing applications | All five application/root Argo CD Applications Synced/Healthy |

DinD certificate generation briefly produced startup/readiness probe failures;
both containers then became Ready without restarts. The controller's update-site
DNS check is blocked by its retained egress hold; this did not prevent startup
or worker connections. Controller startup took about two minutes on the slow lab.

An early idle sample was controller 47m/316Mi, CI agent 54m/63Mi, DinD 16m/16Mi
and publisher 16m/62Mi, within configured bounds. These observations and the tiny
Docker smoke do not establish full application CI capacity or cache sizing.

Six publisher-source fixture tests, five deployment guard tests and five runtime
verifier tests passed. They cover pinned bytes, changed/unsafe source rejection,
existing Secret preservation, refusal of an active controller/enabled jobs,
online/offline agent acceptance, current admin preservation and secret-safe
diagnostics. Seven audit fixtures had already passed before scan deferral.
Shell/Python syntax, Kustomize rendering and diff whitespace checks passed.
No new vulnerability scan was run after the deferral.

## Remaining Phase 9 work

Review preserved pipelines/settings with the operator
before adapting repository/promotion targets or enabling execution. Existing
direct STAGE pushes remain inactive. Controlled application CI, verified-artifact
publication, reviewed promotion, rollback and schedules remain unverified.
Vulnerability remediation and a fresh complete image gate are deferred.
Current K3s PostgreSQL contents and the read-only application checkout are
unchanged. No Git push, PROD mutation, VM100 retirement or NAT change occurred.
