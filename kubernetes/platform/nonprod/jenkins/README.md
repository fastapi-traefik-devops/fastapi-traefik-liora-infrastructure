# Jenkins controller foundation (prepared, not deployed)

The image is the unchanged running PoC controller, published to GHCR at
`ghcr.io/fastapi-traefik-devops/liora-jenkins-controller:phase8-b98a22e` and pinned
in the Deployment by digest. Its `/usr/share/jenkins/ref/plugins.txt` SHA-256
matches `../../upstream/infra/jenkins-host/plugins.lock.txt`:
`bdd7ac49ab8d0d82aecefb51e80005c08d3d9a3c8d705d44de10d93c73cca214`.
The preserved Dockerfile and locks remain the rebuild source; no Jenkins core
or plugin upgrade was performed. The old controller/containers/home are intact.

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

Server dry-run passed. Deployment is on hold behind the
[Admin VIP status ownership decision](../../proposals/README.md) and the required
NONPROD/PROD monitoring sequence. No Jenkins Pods or PVCs have been created.
