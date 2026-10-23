# Jenkins controller foundation

The default overlay remains the Phase 8 foundation for fresh bootstrap. The
current Phase 9 controller uses the [`agents/`](agents/kustomization.yaml) overlay,
which extends [`held/`](held/kustomization.yaml) with the two connected workers;
do not apply the default overlay over that controller as routine reconciliation.
It would switch back to the retained foundation home. The foundation manifests
are now under `base/`; image, resources and initial-login behavior are unchanged.

The image is the unchanged running PoC controller, published to GHCR at
`ghcr.io/fastapi-traefik-devops/liora-jenkins-controller:phase8-b98a22e` and pinned
in the Deployment by digest. Its `/usr/share/jenkins/ref/plugins.txt` SHA-256
matches `../../upstream/infra/jenkins-host/plugins.lock.txt`:
`bdd7ac49ab8d0d82aecefb51e80005c08d3d9a3c8d705d44de10d93c73cca214`.
The preserved Dockerfile and locks remain the rebuild source; no Jenkins core
or plugin upgrade was performed. Legacy named volumes and private backups remain;
the operator's later Docker prune removed stopped containers/local images, so
legacy recovery requires container recreation as described in runbook 17.

Minimal JCasC retains the source security realm/matrix, with zero executors,
no nodes/clouds/jobs, disabled inbound-agent listener and native URL `.16:8085`.
Only a fresh foundation password is mounted. No source Job DSL, GitHub App
keys, GHCR publishing credential, polling or schedules are loaded.

Persistent home is a 5Gi local-path RWO PVC. The controller requests 100m/512Mi,
limits 1 CPU/768Mi and caps heap at 384Mi. It runs as UID/GID 1000 without an API
service-account token. Startup allowance is 15 minutes for this slow lab.
A single-replica Recreate rollout avoids two controllers writing the same home.

Use `scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod
--component jenkins` through `scripts/local-python.sh` to supply the login and
namespace-scoped registry pull Secret. Private recovery data stays under ignored
`.local-work/private/platform/`; the new foundation is not a backup or migration
of old Jenkins state. Phase 9 handles consistent transfer, users/credential IDs,
history, build agents, isolated Docker and trusted publishing. Do not restart
legacy Docker containers or activate jobs during foundation setup.

At Phase 8 acceptance, the controller was Ready, its PVC Bound, and native browser
login passed. The mounted plugin lock matches the preserved source. Authenticated
API checks found zero jobs, zero agents and zero controller executors. The
[approved status guard](../../../../docs/testreports/PHASE8_ADMIN_VIP_DECISION.md)
protects its VIP status. The subsequent held restore is described below; working
CI remains deferred within Phase 9.

## Held migration overlay

The held overlay keeps the same controller image, service, login Secret and
resource limits, but mounts the separate 5Gi `jenkins-home-migrated` PVC.
`jenkins-home` remains intact for rollback. The restore helper backs up the
stopped foundation before transferring any state to the new volume.

The migration JCasC defines the same local realm and admin matrix without a
user/password declaration, so it uses the preserved user files without resetting
the current admin password. It imports no Job DSL, agents or clouds. Private
job configuration, non-admin users, credentials and encryption material come
from the validated stopped archive; current admin data replaces only the legacy
admin profile at the path determined by the preserved user-directory HMAC key.
Nothing private is generated into Git.

An init container refuses startup without the restored configuration, encryption
material, admin profile, quiet-mode hook and verified-transfer marker. A selected
NetworkPolicy denies all controller egress while it is held; this includes DNS
and external API/registry calls. Administrative replies to allowed incoming
connections remain usable. Jobs, multibranch scanning and Pipeline resume remain
disabled. The old source, schedules and promotion pipeline must not be activated
unchanged; follow [runbook 17](../../../../runbooks/17-migrate-jenkins-ci.md).

## Pinned publisher source

The separate publisher still expects the application's `ci/` files at
`/opt/phase1-ci`. Prepare that input with
[`prepare-jenkins-publisher-source.py`](../../../../scripts/kubernetes/prepare-jenkins-publisher-source.py)
using `--output` for a new local JSON path. The prepared pin reads all 27 files
from Git objects at application commit `d87b3c9599c5b79dfc6b6751739a110ecbb2ba96`,
verifies object hashes and produces an immutable ConfigMap named
`jenkins-publisher-ci-d87b3c9599c5` in `jenkins-publisher`. It neither executes
those helpers nor applies the bundle. The application checkout is read-only;
mutable working-tree changes are excluded. The reviewed source commit and bundle
hash are recorded in annotations. Existing output is never overwritten.

The authorized live cycle installed `jenkins-publisher-ci-d87b3c9599c5`;
retain the earlier `jenkins-publisher-ci-b98a22e48527` bundle for rollback.
`--observer` emits a separate one-file, immutable
`jenkins-acceptance-ci-d87b3c9599c5` bundle for the zero-replica standalone
[`acceptance/`](acceptance/kustomization.yaml) overlay. That overlay is not included
by `agents/`; its limited STAGE read-only RBAC and future inbound node require
explicit live approval. It never receives publisher credentials.

Mount this bundle read-only for the publisher, never from an untrusted build
checkout. Its presence does not authorize executing the preserved legacy
promotion workflow. The deployment helper prepares the same bundle directly
and retains a private copy alongside the deployment evidence.

## Initial live cycle

`initial-cycle/` composes the existing two-agent overlay with the controller DNS
and public HTTPS egress needed for GitHub polling/App token generation. It does
not include `acceptance/` or an observer node. Applying it relaxes the current
egress hold and requires explicit live approval. Under that received approval,
the controller GitHub egress policy and reviewed publisher helper/job definition
are installed. Main #15 / publisher #34 completed the first controlled STAGE
cycle and manual deployment verification passed. Main polling is still off
while the related required PR check completes; the next checkpoint enables
only its SCM poll and demonstrates automatic deployment. The initial publisher
stops after the STAGE update; deployment verification remains manual.
PROD is explicitly blocked until automatic acceptance is implemented and live-verified. Retain prepared
observer work for that later increment.

## Connected workers under the hold

The `agents/` overlay keeps the restored controller quiet and jobs disabled,
adding only the original two static nodes and their bounded workloads. CI and
privileged DinD share a work PVC; the publisher has its own PVC and pinned helper
bundle. The daemon has no Service; agents use the existing controller Service via
WebSocket. `deploy-jenkins-agents.py` provisions their private connection Secrets,
checks readiness and online status, and verifies mounted source hashes.

The Docker build/bind smoke and current admin API/browser checks passed with
both agents online. Application pipelines, publishing and schedules remain
inactive pending review. The operator deferred vulnerability remediation and
further image scans for this educational deployment. See the
[worker report](../../../../docs/testreports/PHASE9_WORKERS.md) and
[runbook 17](../../../../runbooks/17-migrate-jenkins-ci.md) for recovery, execution
and the retained zero-agent/foundation rollback boundaries.
