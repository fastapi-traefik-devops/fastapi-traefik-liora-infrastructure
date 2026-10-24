# Publish application routing and trusted TLS

**Where:** Reviewed infrastructure checkout and private management access.

> [!IMPORTANT]
> Preserve independent cluster, namespace, database and GitOps boundaries.
> This procedure provisions routing and certificates; it does not restore
> application data or change application image versions.

## 1. Inspect and provision the edge

- [ ] Check that VM ID `240`, address `192.168.77.240`, and Proxmox capacity
      are available. Review the [edge module](../edge/haproxy/README.md)
      Terraform plan: **one** new edge VM, no changes or destruction of
      existing VMs.
- [ ] Use protected recovery inputs and retain the module's local Terraform
      state in the operator archive.

> [!NOTE]
> The existing Debian template has a 200GiB thin disk; this module does
> not shrink or overwrite it.

- [ ] Apply the reviewed Terraform module, then the linked Ansible playbook:

```sh
terraform -chdir=edge/haproxy/terraform init
terraform -chdir=edge/haproxy/terraform plan -out=edge.tfplan
terraform -chdir=edge/haproxy/terraform apply edge.tfplan
ansible-playbook -i edge/haproxy/ansible/inventory.yml edge/haproxy/ansible/site.yml
```

- [ ] Allow cloud-init and package upgrades to finish. Confirm the SSH
      identity is authorized on the new VM; a forwarded agent can avoid
      copying private keys onto VM 200.
- [ ] Validate `/etc/haproxy/haproxy.cfg` with `haproxy -c -f`. Require
      an active `haproxy` service. Certificate issuance runs in Kubernetes.

> [!NOTE]
> HAProxy accepts application Host/SNI names only. TLS passes through to
> Traefik. Its backend sets are ServiceLB node addresses `.201`–`.203`
> and `.211`–`.213`, never API VIPs `.11`/`.12`. Dedicated floating
> ingress VIPs remain a later option.

> [!WARNING]
> Do not print tokens or store them in tracked tfvars.

## 2. DNS and certificate prerequisites

- [ ] Obtain the **current** Proxmox public IPv4. Check for conflicting
      A/AAAA/CNAME records in the Cloudflare-managed `aprt.info` zone.
- [ ] Create or verify these **DNS-only** records without removing unrelated
      records:

| Host | Origin |
| --- | --- |
| `liora.aprt.info` | Current Proxmox public IPv4 |
| `dev.liora.aprt.info` | Same public IPv4 |
| `stage.liora.aprt.info` | Same public IPv4 |

Do not change unrelated DNS records, proxy settings or Access rules. The
DNS-01 issuer is restricted to the three exact names above. Its only DNS writes
are their `_acme-challenge` TXT records, including cleanup after validation.

## 3. Provision cluster-local certificate management

These steps can run after the environment namespaces exist and before
application deployment. An empty database and public HTTP routing are not
prerequisites for DNS-01 issuance.

- [ ] Use the existing pinned cert-manager installation in each cluster. On a
      fresh cluster, install it before applying Certificate resources:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/cert-manager
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n cert-manager rollout status deployment/cert-manager --timeout=180s
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/cert-manager
kubectl --kubeconfig="$HOME/.kube/config-prod" -n cert-manager rollout status deployment/cert-manager --timeout=180s
```

The same installation retains CNPG/Barman internal certificate management.
Do not install another controller or restore the old namespace-only controller
flags. Wait for the webhook and cainjector Deployments too on a fresh cluster.

- [ ] Restore `recovery/cloudflare-dns-token` privately (mode `0600`) from the
      encrypted recovery kit, or supply a new zone-scoped token. Use
      `Zone:DNS:Edit` and `Zone:Zone:Read` for `aprt.info` only; never reuse R2 keys.
- [ ] Validate and provision the token into `cert-manager` in both clusters:

```sh
python3 scripts/kubernetes/bootstrap-cloudflare-dns.py --apply
```

[Standalone credential provisioning helper](../scripts/kubernetes/bootstrap-cloudflare-dns.py).

- [ ] Apply the issuer independently in both clusters. Its account keys are
      separate Kubernetes Secrets; after disaster recovery it can register fresh
      ACME accounts and reissue certificates without the old edge private keys.

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" apply -k kubernetes/platform/public-certificates
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" wait clusterissuer/letsencrypt-cloudflare --for=condition=Ready --timeout=120s
kubectl --kubeconfig="$HOME/.kube/config-prod" apply -k kubernetes/platform/public-certificates
kubectl --kubeconfig="$HOME/.kube/config-prod" wait clusterissuer/letsencrypt-cloudflare --for=condition=Ready --timeout=120s
```

## 4. Issue, monitor and renew application certificates

- [ ] Each application overlay includes its `certificate.yaml`. For a manual
      fresh deployment the render splitter places it in `config-storage.yaml`;
      Argo CD manages it after application adoption. The Argo projects allow
      namespaced Certificate resources but do not grant cluster-wide writes.
- [ ] For each environment, wait for its namespace-local Certificate:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait certificate/app-tls --for=condition=Ready --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get certificates,certificaterequests,orders,challenges
```

Traefik keeps using `app-tls`. Keys rotate on renewal; cert-manager updates the
Secret without restarting application Pods. Inspect `status.renewalTime`,
`status.notAfter`, Ready/Issuing conditions and Order/Challenge events. DNS
propagation can take minutes. Do not delete working TLS Secrets to retry or run
legacy Secret distribution alongside cert-manager.

- [ ] Verify the exact issued certificate, trust chain and hostname at all
      ingress nodes and HAProxy (example DEV):

```sh
bash scripts/local-python.sh scripts/kubernetes/verify-public-certificate.py dev --output .local-work/tls/dev.json
```

[Standalone TLS verification helper](../scripts/kubernetes/verify-public-certificate.py).
Add `--public` from a network with a working public path. Without that flag the
check establishes trusted private ingress/edge serving, not Internet reachability.
Repeat with STAGE and PROD. Store results with the operational incident/exercise.

- [ ] To test renewal deliberately, install the checksum-pinned CLI and renew
      only the selected application Certificate (example NONPROD DEV):

```sh
bash scripts/kubernetes/install-cmctl.sh
.local-work/tools/cmctl-v2.6.1 --kubeconfig="$HOME/.kube/config-dev-stage" renew app-tls -n app-dev
```

[Standalone pinned CLI installer](../scripts/kubernetes/install-cmctl.sh).
Record the prior revision/serial, wait for a larger revision and Ready condition,
then repeat certificate verification and application acceptance. A Ready condition
alone can remain true for the old certificate during renewal. Do not use
`--all` or renew unrelated CNPG certificates as part of this exercise.

If issuance/renewal fails, inspect DNS-01 events, token validity/scope,
Cloudflare and ACME API access and DNS propagation. Preserve the currently
served Secret while fixing the cause. Changing a token uses the provisioning
helper; do not print Secret data or API responses. Alerting integration specific
to public certificate expiry is not implemented by this procedure.

## 5. Align HTTPS configuration and publish 443

- [ ] Keep STAGE/PROD HTTPS origins and TLS references. Change DEV's
      origin/CORS to `https://dev.liora.aprt.info` where needed; retain its
      documented environment setting, single-worker command and `app-tls` reference.
- [ ] Publish the reviewed infrastructure change and confirm Argo CD
      reconciliation. Keep administrative Services private, with no ingress.

- [ ] Verify namespace TLS through cluster node addresses. After DEV/STAGE
      certificates exist, set `liora_tls_nonprod_enabled: true` in the
      reviewed edge inventory and rerun its playbook.
- [ ] Check the private edge with normal certificate validation and SNI.
      **Only after** every selected route serves a matching trusted
      certificate, publish HTTPS on Proxmox:

```sh
python3 /path/to/configure-liora-edge-nat.py --https
```

- [ ] Recheck VM 200 SSH and all pre-existing forwarding rules after
      publishing HTTPS.

> [!NOTE]
> [The NAT helper](../scripts/proxmox/configure-liora-edge-nat.py) leaves HTTP
> for HTTPS redirection. A syntax check and enabled
> loader do not establish reboot persistence; verify that in a separately
> scheduled reboot.

## 6. Acceptance and rollback boundary

- [ ] For **each** hostname, confirm public DNS, valid certificate
      hostname/chain/expiry, HTTP→HTTPS redirect, backend health, real
      browser login, item create/read/update/reload, and environment isolation.
- [ ] Record image IDs, namespace, cluster, and Argo CD Synced/Healthy
      status.
- [ ] Confirm unknown SNI and nonapplication hosts cannot reach Argo CD,
      Adminer, monitoring, or another environment through the public edge.

- [ ] Run the browser check through the private edge to verify canonical
      HTTPS with SNI, certificate validation, and browser origin. Example
      for DEV:

```sh
export environment=dev namespace=app-dev
export recovery_dir="$HOME/fastapi-traefik-liora-infrastructure/recovery"
export render_dir="$PWD/.local-work/acceptance/$environment"
export acceptance_url=https://dev.liora.aprt.info
export acceptance_address=192.168.77.240
bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
```

- [ ] Repeat with matching STAGE/PROD variables. Obtain an independent
      external-browser check; the private-edge test does not prove external
      reachability.
- [ ] Compare environment markers in both directions. Remove only the
      synthetic items and confirm their absence in the API and database.

> [!NOTE]
> [The browser check](../scripts/kubernetes/verify-application-ui.py) uses
> `acceptance_address` as a Chromium-only IPv4 resolver override. Its
> default is loopback for the private-forward procedure. Normal certificate
> validation remains enabled.

- [ ] Check private Argo CD and Adminer access independently.

### If enabling Cloudflare proxying

- [ ] After the origin has a trusted certificate, use Full (strict) and
      repeat public browser/API acceptance through the proxied path.
      Record each DNS record's proxy state in the phase report.

> [!NOTE]
> DNS-only origin acceptance does not establish a proxied Cloudflare path.

### If routing must be rolled back

> [!WARNING]
> Preserve database PVCs and Secrets. Restore the exact backed-up NAT
> configuration or prior reviewed ingress commit. Do not flush host rules,
> delete a namespace/PVC, or replace unrelated DNS records.

### Historical migration and recovery

The one-time edge Certbot/distribution handover, preserved private rollback
artifacts and execution evidence belong in
[the Phase 11 report](../docs/testreports/PHASE11_REPORT.md). Do not install the
legacy distribution timer on fresh deployments or disaster recovery.

Rebuild infrastructure with the [recovery navigator](../01-Disaster_recovery.md),
then provision the DNS token/issuer and reissue certificates using this runbook.
Application database restoration is a separate recovery step; certificate
readiness does not establish restored data or application acceptance.

References: [K3s ServiceLB](https://docs.k3s.io/networking/networking-services),
[ACME challenge types](https://letsencrypt.org/docs/challenge-types/), and
[cert-manager Cloudflare DNS-01](https://cert-manager.io/docs/configuration/acme/dns01/cloudflare/).
