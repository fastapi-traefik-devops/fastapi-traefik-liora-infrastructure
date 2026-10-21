# Private platform access and monitoring

**Deployment hold:** the initial NONPROD installation exposed a K3s ServiceLB
status-ownership conflict. Do not run the deployment sequence further until the
[ownership decision](../kubernetes/platform/proposals/README.md) is resolved.
The Phase 8 report records partial deployment; this is not a completed runbook
acceptance claim.

Phase 8 adds IP-and-port access through the existing Tailscale subnet route.
Use this checkout and explicit kubeconfigs. The API VIPs, public Traefik,
HAProxy, DNS, legacy VM 100 and its NAT rules stay under their existing owners.
Do not perform failover/reboot/load tests in this procedure.

## Ownership and preparation

`kubernetes/platform/upstream/` preserves selected source history and is not an
installation entrypoint. Active platform manifests are applied by the operator
from this repository. Helm owns the `monitoring` release and its CRDs; kubectl
owns the additional dashboards, monitors, rules and private Services. These
resources are not also attached to an Argo CD platform Application.

Existing application Services are unchanged. Each environment overlay adds a
separately named `adminer-private` Service. On the current installation apply
only this new file, preserving database resources and avoiding unnecessary
prestart hook execution. It has no Argo tracking annotation while local changes
are unpublished. Publishing the reviewed overlay later lets its existing Argo
Application adopt the identical Service. Do not add a second platform owner.
On a fresh installation the environment overlay includes it automatically.

The services-only kube-vip v1.2.3 uses ARP, `svc_election=false`, and the common
`kube-system/liora-admin-services` lease. It watches only LoadBalancer class
`liora.aprt.info/admin-vip`, with legacy class handling disabled. API kube-vip
keeps its original lease and metrics port 2112; this instance uses 2113. Services
explicitly set `kube-vip.io/loadbalancerIPs` and disable NodePort allocation.
`externalTrafficPolicy: Cluster` allows the VIP leader to forward to a Pod on
another node. VIP leadership does not provide replicated local storage.

Pinned source behavior:
[kube-vip ARP worker v1.2.3](https://github.com/kube-vip/kube-vip/blob/v1.2.3/pkg/manager/worker/arp.go),
[class filtering](https://github.com/kube-vip/kube-vip/blob/v1.2.3/pkg/services/watch_services.go),
[environment names](https://github.com/kube-vip/kube-vip/blob/v1.2.3/pkg/kubevip/config_envvar.go).

## NONPROD access first

Review the files and server validation before applying:

```bash
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply --dry-run=server -k kubernetes/platform/nonprod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f kubernetes/apps/liora/overlays/dev/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f kubernetes/apps/liora/overlays/stage/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system rollout status daemonset/kube-vip-admin --timeout=10m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system get lease liora-admin-services plndr-cp-lock
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get services -A -l liora.aprt.info/access=private-admin
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system get daemonsets
```

Require exactly one Admin VIP owner, the separate lease, expected Service IPs,
no administrative `svclb-*` workloads and an unchanged Traefik/API VIP. From a
Tailscale client open Argo CD `https://192.168.77.16:8080`, DEV Adminer
`http://192.168.77.16:8081`, STAGE Adminer `http://192.168.77.16:8082`.
Argo uses native HTTPS and its bootstrap certificate; a warning is expected.
Adminer uses each environment's existing database credentials.

## Per-cluster monitoring

Use Helm 3 and pinned kube-prometheus-stack **92.2.0**. The chart is downloaded
to ignored storage; compare its SHA-256 with `kubernetes/platform/chart-lock.json`
before installation. Do not pass passwords through Helm values or arguments.

```bash
mkdir -p .local-work/charts
helm pull kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts --version 92.2.0 --destination .local-work/charts
sha256sum .local-work/charts/kube-prometheus-stack-92.2.0.tgz
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod --component monitoring
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$HOME/.kube/config-dev-stage" --namespace monitoring --values kubernetes/platform/nonprod/monitoring/values.yaml --wait --timeout 20m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/monitoring
```

[Standalone credential bootstrap script](../scripts/kubernetes/bootstrap-platform-secrets.py).
It preserves existing login Secrets and writes new random credentials only to
`.local-work/private/platform/<cluster>-<component>.json` with mode 0600.
Include these private inputs in the operator's protected recovery archive;
never add them to Git. Losing this file does not rotate an existing Secret.
Recovery with an existing Secret preserves it; a fresh cluster reuses the input
if supplied. Reapplying manifests does not restore PVC data.

Both clusters retain the PoC budget: one Prometheus (100m/512Mi requested,
500m/1536Mi limit), retention 3 days/1500MB and 2Gi PVC; one Alertmanager
(20m/64Mi, 100m/128Mi) with 256Mi PVC; Grafana (50m/128Mi, 300m/384Mi) without
persistent UI state. Dashboards/datasource are provisioned from Git. Node
Exporter runs once per node; operator and kube-state-metrics use bounded source
budgets. All PVCs use `local-path`, remain node-bound, and are not replicas.
External alert delivery is disabled (`pending-destination` receiver) until the
operator agrees it. Alert evaluation and the private UI remain available.

Verify all targets and rules load, dashboard identity/namespaces match the
cluster, and native Grafana login works. Prometheus and Alertmanager use their
native trusted-subnet access model. Native URLs are IP-and-port; no extra TLS,
ingress, authentication proxy, DNS, Tailscale policy or firewall is installed.

## PROD after NONPROD functional readiness

```bash
kubectl --kubeconfig="$HOME/.kube/config-prod" apply --dry-run=server -k kubernetes/platform/prod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/prod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -f kubernetes/apps/liora/overlays/prod/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-prod" -n kube-system rollout status daemonset/kube-vip-admin --timeout=10m
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster prod --component monitoring
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$HOME/.kube/config-prod" --namespace monitoring --values kubernetes/platform/prod/monitoring/values.yaml --wait --timeout 20m
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/prod/monitoring
```

The cluster has separate credentials, storage, lease and monitoring state.
Use `.17:8080` for Argo, `.17:8081` for PROD Adminer. Both clusters expose native
HTTP Grafana `:3000`, Prometheus `:9090`, Alertmanager `:9093`. There is no PROD
Jenkins. Check for one VIP owner and absence of administrative ServiceLB Pods
as above, using the PROD kubeconfig.

## NONPROD Jenkins foundation

The controller image is the existing PoC image published without rebuilding or
changing core/plugins. Its plugin lock matches the preserved source. The active
manifest pins the reviewed GHCR digest; Kubernetes receives registry credentials
from ignored `recovery/.env`. No existing Docker controller is restarted.

```bash
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod --component jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=20m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get pvc
```

[Standalone credential bootstrap script](../scripts/kubernetes/bootstrap-platform-secrets.py).

Open `http://192.168.77.16:8085`; use the private foundation login input. Jenkins
has a 5Gi local-path home, requests 100m/512Mi and limits 1 CPU/768Mi, with Java
heap capped at 384Mi. JCasC sets its native URL, zero controller executors, no
agents, no clouds, no jobs and a disabled inbound-agent listener. Only the login
Secret is mounted. Existing source Job DSL, polling, schedules and publisher
credentials are deferred to Phase 9, along with consistent old-home backup,
state/user/history transfer, agents and working CI. This fresh foundation does
not constitute migration or backup of the old controller's state.

## Acceptance, recovery and rollback

Record actual readiness, browser logins, metrics/rules and endpoint map in the
Phase 8 report. Verify original application PVC identities, Argo health, API VIPs
and public application URLs. Inspect public routing for absence of new admin
routes; verify the new interfaces are not exposed on the public origin. Legacy
VM 100 routes are outside this change, so their existence is not evidence that
a new Admin VIP is public. Never retire VM 100 during Phase 8.

For an access-only rollback, delete the exact new private Service files first,
then remove only `kube-vip-admin` and its dedicated RBAC via its kustomization.
Do not delete `kube-vip-ds`, `plndr-cp-lock`, Traefik or existing application
Services. Once published, change the application overlay source before removal
to prevent Argo self-heal restoring it. Keep all database/Jenkins PVCs.

For monitoring recovery, preserve both monitoring PVCs and private Grafana
inputs; inspect `helm history monitoring` in the explicit cluster before a
reviewed `helm rollback`. Do not uninstall to fix an ordinary readiness delay.
Chart CRDs are shared cluster definitions; do not delete them during rollback.
A Jenkins manifest reapply preserves its home; a fresh home creates a new
foundation only. Restoring working CI state belongs to the Phase 9 procedure.
Do not claim tested failover, host/storage recovery, notification delivery or
scheduled renewals from these functional checks.
