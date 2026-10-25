# Configure private platform access and monitoring

**Where:** Management VM 200, infrastructure repository root.

**Order:** NONPROD, then PROD.

## Preconditions

- [ ] Complete K3s and Tailscale setup.
- [ ] Confirm API/node identities with explicit kubeconfigs.
- [ ] Reserve Admin VIPs `.16` for NONPROD and `.17` for PROD.
- [ ] Preserve application Secrets/PVCs, API VIPs and public Traefik ownership.
- [ ] Prepare Helm and the protected platform credential files.

## Address reference

| Interface | NONPROD | PROD |
| --- | --- | --- |
| Argo CD | `https://192.168.77.16:8080` | `https://192.168.77.17:8080` |
| Grafana | `http://192.168.77.16:3000` | `http://192.168.77.17:3000` |
| Prometheus | `http://192.168.77.16:9090` | `http://192.168.77.17:9090` |
| Alertmanager | `http://192.168.77.16:9093` | `http://192.168.77.17:9093` |
| Adminer DEV / STAGE | `.16:8081` / `.16:8082`, HTTP | — |
| Adminer PROD | — | `http://192.168.77.17:8081` |
| Jenkins | `http://192.168.77.16:8085` | — |

Use native service authentication and protocols over Tailscale. Do not create
public administrative routes, private ingress or manual forwarding dependencies.

## 1. Configure private administrative access

- [ ] Select the cluster:

```sh
cluster=nonprod
case "$cluster" in
  nonprod) kubeconfig="$HOME/.kube/config-dev-stage" ;;
  prod) kubeconfig="$HOME/.kube/config-prod" ;;
  *) echo 'Choose nonprod or prod' >&2; exit 1 ;;
esac
export cluster kubeconfig
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
```

- [ ] Apply the status-ownership guard before the Admin VIP controller/Services:

```sh
kubectl --kubeconfig="$kubeconfig" apply -f kubernetes/platform/base/admin-access/status-ownership.yaml
kubectl --kubeconfig="$kubeconfig" apply --dry-run=server -k "kubernetes/platform/$cluster/admin-access"
kubectl --kubeconfig="$kubeconfig" apply -k "kubernetes/platform/$cluster/admin-access"
kubectl --kubeconfig="$kubeconfig" -n kube-system rollout status daemonset/kube-vip-admin --timeout=10m
kubectl --kubeconfig="$kubeconfig" -n kube-system get lease liora-admin-services plndr-cp-lock
kubectl --kubeconfig="$kubeconfig" get services -A -l liora.aprt.info/access=private-admin
```

- [ ] Require the correct explicit Admin VIP, a separate shared administrative leader, zero administrative NodePorts and no administrative `svclb-*` workloads.
- [ ] Confirm API VIP and public Traefik ownership remain unchanged.
- [ ] Let application overlays own their `adminer-private` Services; do not apply a second database/application owner.

The dedicated controller uses `liora.aprt.info/admin-vip`, lease
`kube-system/liora-admin-services` and host-network port 2113. API kube-vip uses
its own lease and port 2112. Keep the admission guard while private Services exist.

## 2. Install monitoring

- [ ] Download the pinned chart and compare SHA-256 with [chart-lock.json](../kubernetes/platform/chart-lock.json):

```sh
mkdir -p .local-work/charts
helm pull kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts --version 92.2.0 --destination .local-work/charts
sha256sum .local-work/charts/kube-prometheus-stack-92.2.0.tgz
```

- [ ] Stop on a checksum mismatch.
- [ ] Restore protected Grafana credentials for recovery; for a new installation use the credential bootstrap:

```sh
bash scripts/local-python.sh scripts/kubernetes/bootstrap-platform-secrets.py --cluster "$cluster" --component monitoring
```

Standalone script: [bootstrap-platform-secrets.py](../scripts/kubernetes/bootstrap-platform-secrets.py).

The helper preserves existing Secrets. New private platform records go to
`.local-work/private/platform/<cluster>-monitoring.json`; preserve them off-host.

- [ ] For initial installation, submit the chart without waiting so its Prometheus resource exists for Slack credential provisioning:

```sh
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$kubeconfig" --namespace monitoring --values "kubernetes/platform/$cluster/monitoring/values.yaml"
```

- [ ] Provision the cluster's Slack Secret using [Slack operations, section 1](../docs/operations/SLACK_ALERTING.md#1-provision-notification-credentials).
- [ ] Complete chart reconciliation and install additional resources:

```sh
helm upgrade --install monitoring .local-work/charts/kube-prometheus-stack-92.2.0.tgz --kubeconfig "$kubeconfig" --namespace monitoring --values "kubernetes/platform/$cluster/monitoring/values.yaml" --wait --timeout 20m
kubectl --kubeconfig="$kubeconfig" apply -k "kubernetes/platform/$cluster/monitoring"
```

- [ ] Apply backup monitoring using [runbook 19](19-cnpg-r2-backup-pitr.md#5-monitor-and-respond).
- [ ] Confirm Prometheus/Alertmanager PVCs are Bound, targets/rules load, Grafana login works and dashboards identify the selected cluster.
- [ ] Complete notification delivery checks using Slack operations before repeating in PROD.

Helm owns the monitoring release and CRDs. Kubernetes manifests own additional
rules, monitors, dashboards and private Services. Do not edit generated operator
resources or install a competing platform owner. Grafana dashboards/datasources
are provisioned from Git; local-path metrics storage is node-bound.

## 3. Retrieve credentials and check browser access

- [ ] Open a private, unrecorded terminal and run:

```sh
python3 recovery/show_passwords.py
```

Standalone script: [show_passwords.py](../recovery/show_passwords.py).

- [ ] Confirm plaintext display only in that private session. Do not save its output in logs or Git.
- [ ] Use replacement Argo credentials after password rotation; the initial Secret does not contain a rotated password.
- [ ] Log in to Argo CD, Grafana and Adminer from a Tailscale client.
- [ ] Check Prometheus `/targets`, `/rules` and Alertmanager routing/active alerts.
- [ ] Install Jenkins through [runbook 17](17-migrate-jenkins-ci.md).

## 4. Completion checks

- [ ] Run the VIP/ownership check for each cluster:

```sh
bash scripts/local-python.sh scripts/kubernetes/verify-admin-vip.py --cluster "$cluster" --check-admission
```

Standalone script: [verify-admin-vip.py](../scripts/kubernetes/verify-admin-vip.py).

- [ ] Audit monitoring:

```sh
bash scripts/local-python.sh scripts/kubernetes/audit-monitoring-alerts.py --cluster "$cluster" --output ".local-work/private/$cluster-alerting-audit.json"
```

Standalone script: [audit-monitoring-alerts.py](../scripts/kubernetes/audit-monitoring-alerts.py).

- [ ] Confirm public routing has no administrative endpoints and application HTTPS remains functional.
- [ ] Repeat sections 1–4 in PROD after NONPROD checks pass.

**Done when:** Correct private addresses and ownership, native logins, healthy monitoring and notification routing are available independently in each cluster.

## Failure response

- [ ] For missing VIP/status, inspect the guard, lease, controller logs and Service endpoints before replacing resources.
- [ ] For monitoring failure, preserve PVCs and credentials; inspect Helm history and operator events.
- [ ] Revert the reviewed configuration or use the selected Helm revision. Restore separately managed rule/dashboard manifests separately.
- [ ] To remove administrative exposure, remove the exact private Services before their controller and ownership guard. Keep API kube-vip, Traefik and all data volumes.
