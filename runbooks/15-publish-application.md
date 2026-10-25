# Publish application routing and trusted TLS

**Where:** Management VM 200, from the infrastructure checkout. Use the
Cloudflare console for DNS checks and a separate client for public HTTPS tests.

> [!IMPORTANT]
> Preserve independent cluster, namespace, database and GitOps boundaries.
> This procedure provisions routing and certificates; it does not restore
> application data or change application image versions.

## 1. Inspect and provision the edge

- [ ] Check VM ID `240`, address `192.168.77.240`, and Proxmox
      capacity. On an empty host, expect one new edge VM in the
      [edge module](../edge/haproxy/README.md) plan. On a rebuilt host,
      compare existing VM 240 and Terraform state first.
- [ ] Stop on an unreviewed change or destruction of an existing VM.
- [ ] Use protected recovery inputs and retain the module's local Terraform
      state in the operator archive.

> [!NOTE]
> Check the source template disk size and planned edge disk size.
> The module does not shrink existing disks.

- [ ] Apply the reviewed Terraform module, then the linked Ansible playbook:

```sh
source recovery/.env
terraform -chdir=edge/haproxy/terraform init
terraform -chdir=edge/haproxy/terraform plan -out=edge.tfplan
terraform -chdir=edge/haproxy/terraform apply edge.tfplan
ansible-playbook -i edge/haproxy/ansible/inventory.yml \
  --private-key recovery/LIORA-id_ed25519 edge/haproxy/ansible/site.yml
```

> [!WARNING]
> On a replacement host or after restoring Terraform state, compare the plan
> with `qm config 240` and the recovered state before applying. Stop if it
> would replace a surviving edge VM or another resource unexpectedly.

- [ ] Allow Cloud-Init and package upgrades to finish. Confirm the
      archived SSH identity works on the new VM.
- [ ] Validate `/etc/haproxy/haproxy.cfg` with `haproxy -c -f`. Require
      an active `haproxy` service. Certificate issuance runs in Kubernetes.

> [!NOTE]
> HAProxy accepts application Host/SNI names only and passes TLS to
> Traefik. It sends traffic to ServiceLB nodes `.201`–`.203` and
> `.211`–`.213`. It does not use API VIPs `.11` or `.12`.

> [!WARNING]
> Do not print tokens or store them in tracked tfvars.

## 2. DNS and certificate prerequisites

- [ ] Obtain the **current** Proxmox public IPv4. Check for conflicting
      A/AAAA/CNAME records in the Cloudflare-managed `aprt.info` zone.
- [ ] In Cloudflare, select zone `aprt.info`, then open **DNS → Records**.
      For each name below, edit the existing A record or select
      **Add record**. Set its content to the current Proxmox public IPv4
      and its proxy status as shown. Save each record.
      [Cloudflare DNS steps](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/).

| Host | A record content | Proxy status |
| --- | --- | --- |
| `liora.aprt.info` | Current Proxmox public IPv4 | DNS only |
| `dev.liora.aprt.info` | Same public IPv4 | Proxied |
| `stage.liora.aprt.info` | Same public IPv4 | Proxied |

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
Use one cert-manager installation per cluster with the configured cluster-wide scope. Wait for the webhook and cainjector Deployments too on a fresh cluster.

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

- [ ] On disaster recovery, complete [database restore and workload startup](20-restore-live-postgresql.md#3-restore-the-database-with-application-writes-held)
      for the selected environment first. That runbook returns here before
      its HTTPS acceptance check. On fresh installation, complete workload
      startup through [runbook 13](13-deploy-application-manifests.md).
- [ ] Each application overlay includes its `certificate.yaml`. For a manual
      fresh deployment the render splitter places it in `config-storage.yaml`;
      the recovery `maintenance.yaml` also carries it while application
      Deployments stay at zero. Argo CD manages it after application adoption. The Argo projects allow
      namespaced Certificate resources but do not grant cluster-wide writes.
- [ ] For each environment, wait for its namespace-local Certificate:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait certificate/app-tls --for=condition=Ready --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get certificates,certificaterequests,orders,challenges
```

Traefik keeps using `app-tls`. Keys rotate on renewal; cert-manager updates the
Secret without restarting application Pods. Inspect `status.renewalTime`,
`status.notAfter`, Ready/Issuing conditions and Order/Challenge events. DNS
propagation can take minutes. Do not delete working TLS Secrets to retry or install a second writer for the TLS Secret.

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
helper; do not print Secret data or API responses. The platform monitoring
configuration scrapes cert-manager for public Certificate readiness, missing
metrics and expiry alerts; see [Slack operations](../docs/operations/SLACK_ALERTING.md).
These internal checks complement the existing external UptimeRobot checks and
do not replace verification of the certificate actually served.

## 5. Align HTTPS configuration and publish 443

- [ ] Confirm each environment uses its canonical HTTPS origin/CORS, single-worker backend command and namespace-local `app-tls` reference.
- [ ] During fresh setup, keep the manually deployed overlay from
      [runbook 13](13-deploy-application-manifests.md) until Argo adoption in
      navigator step 21. During disaster recovery, use the reviewed manual overlay from
      [runbook 20](20-restore-live-postgresql.md#4-reconcile-desired-state-before-opening-application-traffic)
      while Argo remains held; defer Argo adoption to navigator step 20.
      Keep administrative Services private, with no ingress.

- [ ] Verify namespace TLS through cluster node addresses. After DEV/STAGE
      certificates exist, set `liora_tls_nonprod_enabled: true` in the
      reviewed edge inventory and rerun its playbook.
- [ ] Check the private edge with normal certificate validation and SNI.
      Only after every route serves a matching trusted certificate,
      copy the NAT helper from VM 200 to Proxmox:

```sh
scp -i recovery/LIORA-id_ed25519 \
  scripts/proxmox/configure-liora-edge-nat.py \
  root@192.168.77.1:/root/configure-liora-edge-nat.py
ssh -i recovery/LIORA-id_ed25519 root@192.168.77.1
```

- [ ] On Proxmox, find the public-facing interface. Confirm it owns the
      current public route, then pass its name to the helper:

```sh
ip route get 1.1.1.1
read -r -p 'Public-facing bridge/interface: ' public_interface
ip -br address show "$public_interface"
python3 /root/configure-liora-edge-nat.py --https --interface "$public_interface"
nft list table ip custom77_nat
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
export acceptance_cleanup=true
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

### Cloudflare protection/Access

Configure protection/Access for DEV/STAGE and DNS-only access for PROD.
Preserve the environment-specific policy during recovery.

- [ ] In Cloudflare Zero Trust, open
      **Access controls → Applications**. Create or inspect the
      self-hosted applications for `dev.liora.aprt.info` and
      `stage.liora.aprt.info`. Add each public hostname and its
      intended Allow policy. Do not add a PROD Access application.
      [Cloudflare Access steps](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/).
- [ ] With trusted origin certificates, use Full (strict) for proxied
      DEV/STAGE. Check that unauthenticated browser access encounters Access,
      approved users can log in, and PROD remains publicly accessible.
- [ ] Record proxy/Access state. Keep unrelated subdomains and zone-wide settings unchanged.

> [!NOTE]
> Private origin acceptance does not establish an Access-protected browser
> path. The accepted direct-origin bypass remains described in the architecture.

### If routing must be rolled back

> [!WARNING]
> Preserve database PVCs and Secrets. Restore the exact backed-up NAT
> configuration or prior reviewed ingress commit. Do not flush host rules,
> delete a namespace/PVC, or replace unrelated DNS records.

## Rebuild and reissue certificates

- [ ] Rebuild infrastructure using the [disaster recovery procedure](../01-Disaster_recovery.md).
- [ ] Restore the DNS token and provision the issuer using sections 2–3.
- [ ] Reissue application certificates and verify serving using section 4.
- [ ] Complete database recovery and application login/CRUD before releasing the application to users.

**Done when:** Each application hostname serves its matching trusted certificate, HTTPS/login/CRUD passes, environment-specific Access policy is correct, and administrative endpoints remain private.

References: [K3s ServiceLB](https://docs.k3s.io/networking/networking-services),
[ACME challenge types](https://letsencrypt.org/docs/challenge-types/), and
[cert-manager Cloudflare DNS-01](https://cert-manager.io/docs/configuration/acme/dns01/cloudflare/).
