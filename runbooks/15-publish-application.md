# Publish application routing and trusted TLS

**Where:** Reviewed infrastructure checkout and private management access.
Run during authorized Phase 7. Preserve the independent cluster, namespace,
database and GitOps boundaries established in Phases 3–6.

## 1. Inspect and provision the edge

The [edge module](../edge/haproxy/README.md) creates VM 240 at
`192.168.77.240`. Inspect the Terraform plan: one new edge VM, no existing VM
changes or destruction. Verify VM ID/address availability and Proxmox capacity.
Use the protected recovery inputs and retain the module's local Terraform state
in the operator archive. The existing Debian template has a 200GiB thin disk;
this module does not shrink or overwrite it.

Apply the reviewed Terraform module, then the linked Ansible playbook. Allow
cloud-init/package upgrades to complete on the slow lab host. The SSH identity
must be authorized on the new VM; a forwarded agent avoids copying private
keys onto VM 200. Do not print tokens or store them in tracked tfvars.

```sh
terraform -chdir=edge/haproxy/terraform init
terraform -chdir=edge/haproxy/terraform plan -out=edge.tfplan
terraform -chdir=edge/haproxy/terraform apply edge.tfplan
ansible-playbook -i edge/haproxy/ansible/inventory.yml edge/haproxy/ansible/site.yml
```

Validate `/etc/haproxy/haproxy.cfg` with `haproxy -c -f` and require active
`haproxy` and `liora-acme-webroot` services. HAProxy accepts application Host/SNI
names only. TLS passes through to Traefik; its two backend sets are the existing
ServiceLB node addresses `.201`–`.203` and `.211`–`.213`, never API VIPs `.11`/`.12`.
This keeps ServiceLB and avoids another address announcer. Dedicated floating
cluster ingress VIPs remain a later option.

## 2. DNS and certificate prerequisites

Create or verify these records in the Cloudflare-managed `aprt.info` zone:

| Host | Origin |
| --- | --- |
| `liora.aprt.info` | Current Proxmox public IPv4 |
| `dev.liora.aprt.info` | Same public IPv4 |
| `stage.liora.aprt.info` | Same public IPv4 |

The observed origin at Phase 7 discovery was `151.115.96.5`; obtain the current
host address during recovery. Initially use DNS-only records for origin
validation. Check for conflicting A/AAAA/CNAME records before editing; never
remove unrelated zone records. A scoped Cloudflare DNS token may be used from a
protected local file, or the operator may create the records. The existing
recovery version 1 schema has no Cloudflare token field; do not insert unsupported
credentials into it or commit tokens. Do not silently change zone-wide SSL mode
or other settings that affect unrelated applications.

Cloudflare proxying is a separate final check: use Full (strict) with a trusted
origin certificate, then verify the public browser/API path again. Keep the
current record's proxy state explicit in the phase report. DNS-only origin
acceptance does not establish a proxied Cloudflare path.

## 3. Publish HTTP for ACME, preserving existing NAT

On the Proxmox host inspect the entire existing
`/etc/nftables.d/custom77-nat.nft`, active rules, public interface and loader.
Confirm no other service/rule owns public 80/443. The current interface is
`vmbr0`; VM 200 SSH and all unrelated rules must remain intact.

Copy the helper to the host and run it as root. The default adds only port 80,
so HTTPS can remain unpublished until certificates are verified:

```sh
python3 /path/to/configure-liora-edge-nat.py
```

Standalone script: [Preserve and extend the project NAT table](../scripts/proxmox/configure-liora-edge-nat.py).
The helper accepts the existing single-chain table layout, rejects conflicting
port ownership, validates the candidate with `nft -c`, creates a timestamped
backup and applies only the project table. It never flushes the complete ruleset.
Reuse the existing `custom77-nat.service` loader; do not add a second loader.

Write a temporary non-secret challenge file under the edge's
`/var/lib/liora-acme/.well-known/acme-challenge/`, verify it from outside the
private network on every hostname, then remove it. Unknown HTTP Host names must
return 403. This test must pass before requesting certificates; private routing
alone cannot prove an external ACME authority can reach the origin.

## 4. Issue and install namespace-local certificates

The edge has Certbot and a loopback-only HTTP webroot service. For each hostname
whose public DNS and HTTP challenge path are ready, issue a separate certificate
on the edge. Use the operator's real ACME email, or explicitly choose Certbot's
no-email registration option; never invent an operational mailbox.

```sh
sudo certbot certonly --webroot --webroot-path /var/lib/liora-acme \
  --cert-name liora-prod -d liora.aprt.info
```

Repeat with `liora-dev` / `dev.liora.aprt.info` and `liora-stage` /
`stage.liora.aprt.info`. Begin with the ACME staging directory for a new untested
network path if needed; staging certificates are not trusted acceptance evidence.
Preserve certificate state under root-only `/etc/letsencrypt`, outside Git.

Transfer each certificate chain and private key through private SSH to an
operator-owned protected directory, with private keys mode 0600. Avoid printing
key contents or exposing them in process arguments. The Kubernetes helper reads
files in memory, validates explicit SAN, validity and matching public keys, and
sends a namespace-local `app-tls` Secret on stdin with errors suppressed:

```sh
python3 scripts/kubernetes/install-application-tls.py prod \
  --certificate "$HOME/liora-tls/prod/fullchain.pem" \
  --private-key "$HOME/liora-tls/prod/privkey.pem"
```

Standalone script: [Validate and install application TLS](../scripts/kubernetes/install-application-tls.py).
Repeat with `dev` and `stage` and their matching certificate files. The helper
selects the explicit intended kubeconfig, checks its API VIP, and changes only
`app-tls` in the selected app namespace. It does not rotate application or
database credentials. Never commit generated Secret manifests.

Certificate renewal on the edge does not by itself update Kubernetes Secrets.
The management VM runs a daily distribution timer after the edge's Certbot
renewal. It uses its existing SSH identity, whose public key is authorized on
the edge, and its explicit cluster kubeconfigs. No private key needs copying
between management hosts. Verify the edge host key privately before unattended
SSH; the distribution helper requires an existing known-hosts entry.

Install the two helpers together under the management VM's
`/home/root-admin/liora-phase7-edge/certificate-sync/`, then install the supplied
systemd units. The helper pulls only the three fixed certificate paths, keeps
transfers in a private temporary directory and removes the local copies after
validation and Secret installation. It prints only environment/status messages.
The management SSH account currently has the template's existing sudo access
on the edge; narrowing certificate retrieval to a dedicated key/command is
separate hardening work.

```sh
sudo install -m 0644 edge/haproxy/liora-certificate-sync.service /etc/systemd/system/
sudo install -m 0644 edge/haproxy/liora-certificate-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now liora-certificate-sync.timer
sudo systemctl start liora-certificate-sync.service
sudo systemctl show liora-certificate-sync.service -p Result -p ExecMainStatus
```

Standalone script: [Synchronize issued edge certificates](../scripts/kubernetes/sync-edge-certificates.py).
Keep [the TLS installer](../scripts/kubernetes/install-application-tls.py) beside
it. The service uses the system Python with `cryptography` installed. Require
`Result=success`, `ExecMainStatus=0`, an enabled timer, matching served certificate
serials and a successful `certbot renew --dry-run --no-random-sleep-on-renew`
for each production certificate. A successful issuance/distribution test does
not establish a later unattended renewal cycle; monitor the timer and expiry.

## 5. Align HTTPS configuration and publish 443

Keep STAGE/PROD HTTPS origins and TLS references. Change DEV's origin/CORS to
`https://dev.liora.aprt.info`, retain its documented environment setting and
single-worker command, and add a DEV `app-tls` reference. Apply changes through
a reviewed infrastructure commit, publish it and let Argo CD reconcile. Keep
administrative Services private and leave their ingress absent.

Verify namespace TLS directly through the cluster node addresses first. Then
set `liora_tls_nonprod_enabled: true` in the reviewed edge inventory and rerun
the playbook; keep it false while DEV/STAGE certificates are absent. Verify the
private edge using normal certificate
validation and SNI. Only after all selected routes serve matching trusted
certificates, publish HTTPS on the Proxmox host:

```sh
python3 /path/to/configure-liora-edge-nat.py --https
```

Standalone script: [Publish validated application HTTPS forwarding](../scripts/proxmox/configure-liora-edge-nat.py).
HTTP remains limited to challenge serving and HTTPS redirection. Recheck VM 200
SSH and all pre-existing project forwarding rules after the change. A syntax
check and enabled loader do not establish reboot persistence; verify that in a
separately scheduled reboot, not by interrupting the live lab unexpectedly.

## 6. Acceptance and rollback boundary

For every hostname require public DNS, valid hostname/chain/expiry, HTTP→HTTPS
redirect, backend health, real browser login, item create/read/update/reload and
correct environment isolation. Record image IDs, namespace, cluster and Argo CD
Synced/Healthy status. Check that unknown SNI and nonapplication hosts cannot
reach Argo CD, Adminer, monitoring or another environment through this edge.
Repeat acceptance after Cloudflare proxy activation if used.

The reusable browser check can verify canonical HTTPS directly through the
private edge while preserving SNI, certificate validation and browser origin:

```sh
export environment=dev namespace=app-dev
export recovery_dir="$HOME/fastapi-traefik-liora-infrastructure/recovery"
export render_dir="$PWD/.local-work/acceptance/$environment"
export acceptance_url=https://dev.liora.aprt.info
export acceptance_address=192.168.77.240
bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
```

Standalone script: [Verify canonical HTTPS UI and persistence](../scripts/kubernetes/verify-application-ui.py).
Repeat with the matching STAGE/PROD variables. `acceptance_address` is an IPv4
resolver override inside Chromium only; its default remains loopback for the
private-forward procedure. Normal certificate validation stays enabled. This
check does not by itself establish reachability from outside the lab, so obtain
an independent external-browser check as well. After comparing environment
markers in both directions, remove only the synthetic items and confirm their
absence in the API and database.

Check private Argo CD/Adminer access independently. Preserve database PVCs and
Secrets during routing rollback. Restore the exact backed-up NAT/configuration
or prior reviewed ingress commit if needed; never flush host rules, delete a
namespace/PVC, or replace unrelated DNS records as a routing rollback step.

Record actual results and remaining checks in `docs/testreports/PHASE7_REPORT.md`.
Stop before Phase 8. Monitoring and database replacement are separate phases.

References: [K3s ServiceLB](https://docs.k3s.io/networking/networking-services),
[ACME challenge types](https://letsencrypt.org/docs/challenge-types/), and
[Certbot webroot and renewal](https://eff-certbot.readthedocs.io/en/stable/using.html).
