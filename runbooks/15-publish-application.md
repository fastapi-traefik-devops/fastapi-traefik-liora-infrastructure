# Publish application routing and trusted TLS

**Where:** Reviewed infrastructure checkout and private management access.

> [!IMPORTANT]
> Run during authorized Phase 7. Preserve the independent cluster,
> namespace, database, and GitOps boundaries established in Phases 3–6.

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
      active `haproxy` and `liora-acme-webroot` services.

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

> [!NOTE]
> The observed origin at Phase 7 discovery was `151.115.96.5`; it may
> change during recovery. A scoped Cloudflare DNS token may be used from a
> protected local file, or the operator may create the records. Recovery
> schema version 1 has no Cloudflare token field.

> [!WARNING]
> Do not add unsupported credentials to recovery YAML, commit tokens,
> remove unrelated records, or silently change zone-wide SSL settings.

## 3. Publish HTTP for ACME, preserving existing NAT

- [ ] On Proxmox, inspect all of `/etc/nftables.d/custom77-nat.nft`, active
      rules, public interface, and loader. Confirm no other service or rule
      owns public ports 80/443.

> [!NOTE]
> The current public interface is `vmbr0`. VM 200 SSH and unrelated rules
> must remain intact.

- [ ] Copy the NAT helper to Proxmox and run it as root. Its default
      publishes **only port 80**:

```sh
python3 /path/to/configure-liora-edge-nat.py
```

Standalone script: [Preserve and extend the project NAT table](../scripts/proxmox/configure-liora-edge-nat.py).
The helper accepts the existing single-chain table layout, rejects conflicting
port ownership, validates the candidate with `nft -c`, creates a timestamped
backup and applies only the project table. It never flushes the complete ruleset.
Reuse the existing `custom77-nat.service` loader; do not add a second loader.

- [ ] Write a temporary non-secret file under
      `/var/lib/liora-acme/.well-known/acme-challenge/` on the edge.
      Check it from **outside** the private network for every hostname,
      then remove it.
- [ ] Confirm unknown HTTP Host names return 403.

> [!WARNING]
> Stop before requesting certificates if the external challenge check
> fails. Private routing does not prove that ACME can reach the origin.

## 4. Issue and install namespace-local certificates

> [!NOTE]
> The edge has Certbot and a loopback-only HTTP webroot service.

- [ ] For each hostname with working public DNS and HTTP challenge path,
      issue a **separate** certificate on the edge. Use the operator's real
      ACME email or explicitly choose Certbot's no-email option:

```sh
sudo certbot certonly --webroot --webroot-path /var/lib/liora-acme \
  --cert-name liora-prod -d liora.aprt.info
```

- [ ] Repeat with `liora-dev` / `dev.liora.aprt.info` and
      `liora-stage` / `stage.liora.aprt.info`. Preserve certificate state
      under root-only `/etc/letsencrypt`, outside Git.

> [!TIP]
> An untested network path may first use the ACME staging directory.
> Staging certificates are not trusted acceptance evidence.

- [ ] Transfer each certificate chain and private key through private SSH
      to a protected operator-owned directory. Set private keys to mode 0600.
- [ ] Install each namespace-local `app-tls` Secret using the matching files.
      The helper checks SAN, validity, and matching keys. For PROD:

```sh
python3 scripts/kubernetes/install-application-tls.py prod \
  --certificate "$HOME/liora-tls/prod/fullchain.pem" \
  --private-key "$HOME/liora-tls/prod/privkey.pem"
```

[Standalone TLS installer](../scripts/kubernetes/install-application-tls.py).
Repeat with `dev` and `stage` and their matching certificate files. The
helper selects the intended kubeconfig, checks its API VIP, and changes only
`app-tls` in the selected namespace.

> [!WARNING]
> Do not print private keys, expose them in process arguments, or commit
> generated Secret manifests. This step does not rotate application or
> database credentials.

> [!NOTE]
> Edge renewal alone does not update Kubernetes Secrets. VM 200 runs a daily
> distribution timer using its SSH identity and explicit cluster kubeconfigs.
> No private key needs copying between management hosts.

- [ ] Verify the edge host key privately before unattended SSH. The helper
      requires an existing known-hosts entry.
- [ ] Install both helpers under
      `/home/root-admin/liora-phase7-edge/certificate-sync/`, then install
      and start the supplied systemd units:

```sh
sudo install -m 0644 edge/haproxy/liora-certificate-sync.service /etc/systemd/system/
sudo install -m 0644 edge/haproxy/liora-certificate-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now liora-certificate-sync.timer
sudo systemctl start liora-certificate-sync.service
sudo systemctl show liora-certificate-sync.service -p Result -p ExecMainStatus
```

- [ ] Confirm `Result=success`, `ExecMainStatus=0`, an enabled timer,
      matching served certificate serials, and a successful
      `certbot renew --dry-run --no-random-sleep-on-renew` for each
      production certificate. Monitor timer runs and certificate expiry.

> [!NOTE]
> Keep [the TLS installer](../scripts/kubernetes/install-application-tls.py)
> beside [the synchronization helper](../scripts/kubernetes/sync-edge-certificates.py).
> The service uses system Python with `cryptography`. It pulls only the
> three fixed certificate paths, uses private temporary storage, and removes
> copies after installation. The management account's existing sudo access
> on the edge can be narrowed later. A successful issuance/distribution
> test does not prove a later unattended renewal.

## 5. Align HTTPS configuration and publish 443

- [ ] Keep STAGE/PROD HTTPS origins and TLS references. Change DEV's
      origin/CORS to `https://dev.liora.aprt.info`, retain its documented
      environment setting and single-worker command, and add a DEV
      `app-tls` reference.
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
> for challenge serving and HTTPS redirection. A syntax check and enabled
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

### Close out Phase 7

- [ ] Record actual results and pending checks in
      `docs/testreports/PHASE7_REPORT.md`.

> [!NOTE]
> Stop before Phase 8. Monitoring and database replacement are separate
> phases.

References: [K3s ServiceLB](https://docs.k3s.io/networking/networking-services),
[ACME challenge types](https://letsencrypt.org/docs/challenge-types/), and
[Certbot webroot and renewal](https://eff-certbot.readthedocs.io/en/stable/using.html).
