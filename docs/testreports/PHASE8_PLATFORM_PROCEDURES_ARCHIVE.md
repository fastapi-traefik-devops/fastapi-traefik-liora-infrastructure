# Historical procedure record — 16-private-platform-access

Archived on 2026-10-24 before the operational-manual rewrite. This preserves
one-time decisions, commands, observations and original limitations. Statements
about current status describe their original checkpoint. Do not use this record
as the installation or incident-response entrypoint. Operator scripts remain
in their original locations.

Current procedure: [16-private-platform-access.md](../../runbooks/16-private-platform-access.md).

---

# Private platform access and monitoring

**Where:** Reviewed infrastructure checkout with explicit cluster kubeconfigs
and access to the existing Tailscale subnet route.

> [!IMPORTANT]
> Apply the approved native status-ownership guard **before** Admin VIP
> Services. The initial NONPROD installation exposed a K3s ServiceLB
> incompatibility; the [decision record](PHASE8_ADMIN_VIP_DECISION.md)
> explains why class-only isolation is insufficient. See the Phase 8 report
> for actual acceptance boundaries.

> [!NOTE]
> Phase 8 adds IP-and-port access through the existing Tailscale subnet
> route. The API VIPs, public Traefik, HAProxy, DNS, legacy VM 100 and its
> NAT rules stay under their existing owners. This procedure does not
> perform failover, reboot, or load tests.

## Retrieve browser access credentials

- [ ] When browser credentials are needed, run the
      [recovery password helper](../../recovery/show_passwords.py) from the
      repository root:

```bash
python3 recovery/show_passwords.py
```

> [!WARNING]
> The helper displays plaintext passwords after a `Continue? y/n:` prompt.
> Enter `y` only in a private operator session. Any other answer or EOF
> cancels before reading credentials. Keep output out of Git.

It lists URLs and credentials for Application, Adminer, Argo CD, Grafana and
NONPROD Jenkins. Prometheus and Alertmanager have no separate login. The
helper requires Python 3, `kubectl`, and read access to both clusters'
Secrets and ConfigMaps; it does not modify or save cluster data. Private
URLs require Tailscale or equivalent private access.

The default kubeconfigs are `~/.kube/config-dev-stage` and `~/.kube/config-prod`;
override them with `--nonprod-kubeconfig PATH` and `--prod-kubeconfig PATH`.
> [!NOTE]
> Argo CD initial-admin passwords may be stale or absent after rotation.
> Other passwords reflect stored Secrets; the helper does not verify
> logins or display SSH keys and infrastructure API tokens. See the
> [recovery helper documentation](../../recovery/README.md#display-browser-passwords)
> for limitations and exit statuses.

## Ownership and preparation

> [!NOTE]
> `kubernetes/platform/upstream/` preserves source history; it is not an
> installation entrypoint. Helm owns the `monitoring` release and CRDs.
> kubectl owns additional dashboards, monitors, rules and private Services.
> They are not also attached to an Argo CD platform Application.

- [ ] On the current installation, apply only each new
      `adminer-private` Service file as shown below. Preserve database
      resources and avoid an unnecessary prestart hook run.

> [!NOTE]
> Existing application Services are unchanged. The new Service has no Argo
> tracking annotation while local changes are unpublished. Publishing the
> reviewed overlay later lets its existing Argo Application adopt the
> identical Service. A fresh environment overlay includes it automatically.
> Do not add a second platform owner.

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

- [ ] Review the manifests and server validation. Apply the status guard
      **first**, including on a fresh recovery cluster; then apply the
      NONPROD admin access resources:

```bash
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f kubernetes/platform/base/admin-access/status-ownership.yaml
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply --dry-run=server -k kubernetes/platform/nonprod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f kubernetes/apps/liora/overlays/dev/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -f kubernetes/apps/liora/overlays/stage/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system rollout status daemonset/kube-vip-admin --timeout=10m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system get lease liora-admin-services plndr-cp-lock
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get services -A -l liora.aprt.info/access=private-admin
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n kube-system get daemonsets
```

- [ ] Confirm exactly one Admin VIP owner, its separate lease, expected
      Service IPs, no administrative `svclb-*` workloads, and unchanged
      Traefik/API VIPs.
- [ ] From a Tailscale client, open Argo CD
      `https://192.168.77.16:8080`, DEV Adminer
      `http://192.168.77.16:8081`, and STAGE Adminer
      `http://192.168.77.16:8082`.

> [!NOTE]
> Argo uses native HTTPS with its bootstrap certificate; a warning is
> expected. Adminer uses each environment's existing database credentials.

### Argo CD login credentials

> [!NOTE]
> The username is `admin` in both clusters; passwords are separate.

- [ ] If using initial credentials, retrieve the password for the
      corresponding cluster endpoint:

```bash
# NONPROD: https://192.168.77.16:8080
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode
printf '\n'

# PROD: https://192.168.77.17:8080
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 --decode
printf '\n'
```

### If the Argo CD password was rotated

> [!NOTE]
> Use replacement credentials from the protected recovery archive. The
> initial Secret does not provide the replacement password and may have
> been removed.

## Per-cluster monitoring

Use Helm 3 and pinned kube-prometheus-stack **92.2.0**.

- [ ] Download the chart to ignored storage and compare its SHA-256 with
      `kubernetes/platform/chart-lock.json`. Stop on a mismatch.

```bash
mkdir -p .local-work/charts
helm pull kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts --version 92.2.0 --destination .local-work/charts
sha256sum .local-work/charts/kube-prometheus-stack-92.2.0.tgz
```

- [ ] Only after the checksum matches, bootstrap NONPROD monitoring
      credentials and install the chart and additional manifests:

```bash
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod --component monitoring
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$HOME/.kube/config-dev-stage" --namespace monitoring --values kubernetes/platform/nonprod/monitoring/values.yaml --wait --timeout 20m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/monitoring
```

> [!IMPORTANT]
> [The credential bootstrap script](../../scripts/kubernetes/bootstrap-platform-secrets.py)
> preserves existing login Secrets and writes new random credentials only
> to `.local-work/private/platform/<cluster>-<component>.json` with mode
> 0600. Include these inputs in the protected recovery archive, never Git.
> Losing the file does not rotate an existing Secret. Reapplying manifests
> does not restore PVC data.

### Grafana login credentials

> [!NOTE]
> Grafana's login and password are the `username` and `password` fields
> in the cluster-specific JSON file. The bootstrap default username is
> `admin007@liora.aprt.info`.

- [ ] From the checkout where bootstrap ran, read the selected cluster's
      private credential file:

```bash
# NONPROD: http://192.168.77.16:3000
cat .local-work/private/platform/nonprod-monitoring.json

# PROD: http://192.168.77.17:3000
cat .local-work/private/platform/prod-monitoring.json
```

> [!WARNING]
> Both files are Git-ignored recovery inputs, not files supplied by a
> fresh clone. Preserve them in the protected operator archive and keep
> their plaintext contents out of logs.

### Monitoring resources and acceptance

Both clusters adapt the PoC budget: one Prometheus (100m/512Mi requested,
500m/1536Mi limit), retention 3 days/1500MB and 2Gi PVC; one Alertmanager
(20m/64Mi, 100m/128Mi) with 256Mi PVC; Grafana (100m/256Mi, 500m/768Mi) without
persistent UI state. Dashboards/datasource are provisioned from Git. Node
Exporter runs once per node; operator and kube-state-metrics use bounded source
budgets. All PVCs use `local-path`, remain node-bound, and are not replicas.
The original Grafana 384Mi limit caused an observed OOM kill; the larger limit
and 15-minute startup allowance accommodate the current version on this lab.
External alert delivery is disabled (`pending-destination` receiver) until the
operator agrees it. Alert evaluation and the private UI remain available.

- [ ] Check all monitoring targets and rules load, dashboards identify
      the correct cluster and namespaces, and native Grafana login works.

> [!NOTE]
> Prometheus and Alertmanager use native trusted-subnet access. Native
> URLs are IP-and-port; this phase adds no TLS, ingress, authentication
> proxy, DNS, Tailscale policy, or firewall.

## PROD after NONPROD functional readiness

- [ ] Confirm NONPROD access and monitoring are functional before
      deploying the same components in PROD.
- [ ] Apply the guard first, then PROD private access, credentials,
      monitoring chart, and additional manifests:

```bash
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -f kubernetes/platform/base/admin-access/status-ownership.yaml
kubectl --kubeconfig="$HOME/.kube/config-prod" apply --dry-run=server -k kubernetes/platform/prod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/prod/admin-access
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -f kubernetes/apps/liora/overlays/prod/service-adminer-private.yaml
kubectl --kubeconfig="$HOME/.kube/config-prod" -n kube-system rollout status daemonset/kube-vip-admin --timeout=10m
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster prod --component monitoring
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$HOME/.kube/config-prod" --namespace monitoring --values kubernetes/platform/prod/monitoring/values.yaml --wait --timeout 20m
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/prod/monitoring
```

- [ ] With the PROD kubeconfig, confirm one VIP owner, expected Service
      IPs, and no administrative ServiceLB Pods. Check Argo CD at
      `.17:8080` and PROD Adminer at `.17:8081`.

> [!NOTE]
> PROD has separate credentials, storage, lease, and monitoring state.
> Both clusters expose native HTTP Grafana `:3000`, Prometheus `:9090`,
> and Alertmanager `:9093`. There is no PROD Jenkins.

## NONPROD Jenkins foundation

> [!NOTE]
> This installs the existing PoC controller image without rebuilding or
> upgrading core/plugins. The manifest pins its reviewed GHCR digest and
> reads registry credentials from ignored `recovery/.env`. It does not
> restart the existing Docker controller.

- [ ] Bootstrap NONPROD Jenkins credentials, apply the foundation
      manifests, wait for rollout, and inspect its PVC:

```bash
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster nonprod --component jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/nonprod/jenkins
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins rollout status deployment/jenkins --timeout=20m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get pvc
```

[Standalone credential bootstrap script](../../scripts/kubernetes/bootstrap-platform-secrets.py).

- [ ] From the checkout where bootstrap ran, read the Jenkins password
      from the `password` field in the private file:

```bash
cat .local-work/private/platform/nonprod-jenkins.json
```

- [ ] Open `http://192.168.77.16:8085` through private access and log in
      as `admin`. Preserve the Git-ignored credential file in the
      protected operator recovery archive.

Jenkins has a 5Gi local-path home, requests 100m/512Mi and limits 1 CPU/768Mi, with Java
heap capped at 384Mi. JCasC sets its native URL, zero controller executors, no
agents, no clouds, no jobs and a disabled inbound-agent listener. Only the login
Secret is mounted. Existing source Job DSL, polling, schedules and publisher
credentials are deferred to Phase 9, along with consistent old-home backup,
state/user/history transfer, agents and working CI. This fresh foundation does
not constitute migration or backup of the old controller's state.

## Verify the approved guard and native UIs

- [ ] Check the guard, VIP, and native interfaces on NONPROD and PROD:

```bash
bash scripts/local-python.sh scripts/kubernetes/verify-admin-vip.py --cluster nonprod --check-admission
bash scripts/local-python.sh scripts/kubernetes/verify-platform-access.py --cluster nonprod --include-jenkins
bash scripts/local-python.sh scripts/kubernetes/verify-admin-vip.py --cluster prod --check-admission
bash scripts/local-python.sh scripts/kubernetes/verify-platform-access.py --cluster prod
```

[Standalone VIP/ownership verifier](../../scripts/kubernetes/verify-admin-vip.py).
[Standalone native browser verifier](../../scripts/kubernetes/verify-platform-access.py).
The VIP verifier uses only server dry-run status patches for its admission
checks. It checks lease/Service consistency, Ready endpoints, zero NodePorts and
absence of administrative ServiceLB DaemonSets. Add `--check-node-addresses`
with `--known-hosts <trusted-file>` to read all three nodes' interface addresses
through SSH and prove exactly one actual VIP owner; this is an ordinary read,
not a failover test. Obtain host keys from existing trusted provisioning records;
do not disable host-key verification. Browser checks do not save sessions or
credentials, and report only a safe check name/type on error.

> [!NOTE]
> The guard rejects non-owner writes to administrative Service status,
> including manual patches. Removing its binding reintroduces the K3s
> conflict. ServiceLB denied-update retries do not mean the VIP disappeared.
> While these Services are active, keep the guard. During rollback remove
> private Services before the guard and its binding/policy.

### If monitoring status was wiped in a partial installation

- [ ] Apply and verify the guard, then recreate **only** the three new
      private monitoring Services from `monitoring/services.yaml`.

> [!WARNING]
> Do not delete original Services, Pods, PVCs, or the shared VIP controller.
> Recreating these exposure objects lets kube-vip write status again;
> changing annotations alone may not resynchronize a cached instance.
> Fresh installation does not need this repair.

## Acceptance

- [ ] Record readiness, browser logins, metrics/rules, and endpoint map
      in the Phase 8 report.
- [ ] Confirm original application PVC identities, Argo health, API VIPs,
      and public application URLs.
- [ ] Inspect public routing for new admin routes. Confirm the new
      interfaces are not exposed on the public origin.

> [!NOTE]
> Legacy VM 100 routes are outside Phase 8; their existence does not show
> that a new Admin VIP is public. Do not retire VM 100 in this phase. These
> functional checks do not prove failover, host/storage recovery,
> notification delivery, or scheduled renewals.

### If private access must be rolled back

> [!WARNING]
> Delete the exact new private Service files first, then remove only
> `kube-vip-admin` and its dedicated RBAC via its kustomization. Once the
> overlay is published, change its source before removal so Argo self-heal
> does not restore it. Keep database and Jenkins PVCs. Do not delete
> `kube-vip-ds`, `plndr-cp-lock`, Traefik, or existing application Services.

### If monitoring or Jenkins needs recovery

> [!WARNING]
> Preserve both monitoring PVCs and private Grafana inputs. Inspect
> `helm history monitoring` in the explicit cluster before a reviewed
> `helm rollback`. Do not uninstall for an ordinary readiness delay or
> delete shared chart CRDs. Reapplying the Jenkins manifest preserves its
> home; a fresh home creates only a new foundation. Working CI state
> recovery belongs to Phase 9.
