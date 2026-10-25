# Phase 7 report — application HTTPS publication

Status on 2026-10-21: **complete for direct DNS-only origin access**. Phase 8
has not started. Cloudflare proxy mode is not included in this acceptance.

## Source, scope and public path

Work continued in the original infrastructure checkout on `main`, starting from
`5d377642753a0defa0134adb1b828bec6cfc50aa`. Application image pins and imported
source history remain unchanged from source
`b98a22e48527c256193ed65c10307eb574b27ab6`. The application repository and kind
reference deployment were not modified.

All three domains now have A records for the current origin `151.115.96.5`:

| Environment | Canonical URL | Cluster / namespace |
| --- | --- | --- |
| DEV | `https://dev.liora.aprt.info` | dev-stage / app-dev |
| STAGE | `https://stage.liora.aprt.info` | dev-stage / app-stage |
| PROD | `https://liora.aprt.info` | prod / app-prod |

At discovery only PROD resolved. DEV/STAGE records subsequently appeared on the
Cloudflare authoritative nameserver while the DNS question was pending. No DNS
API token was supplied or used, and this agent did not mutate the DNS zone.
The returned origin A records establish DNS-only operation. Cloudflare HTTP
proxying, Full (strict) mode and zone-wide settings were not changed or tested.

The implemented path is public origin TCP 80/443 → Proxmox DNAT → dedicated
HAProxy VM 240 (`192.168.77.240`) → the selected cluster's existing ServiceLB
Traefik node addresses → namespace-local application ingress. Nonprod uses
`.201`–`.203`; PROD uses `.211`–`.213`. These disjoint ingress endpoint pools
are separate from API VIPs `.11`/`.12`. ServiceLB stays enabled; no floating
ingress VIP or competing address announcer was introduced.

## Edge provisioning and host forwarding

Terraform 1.8-compatible configuration with bpg/proxmox 0.111.1 created only
`liora-edge`, VM 240: one vCPU, 1GiB RAM, private vnet77 address, template 9013.
The inherited 200GiB thin ZFS disk was retained. The reviewed plan was one add,
zero changes, zero destruction; apply completed and a subsequent plan reported
no changes. The module validates and formats correctly and has `prevent_destroy`.
The VM was allowed to finish cloud-init and package upgrades on the slow host.

Live module/state/plan are retained on management VM 200 at
`/home/root-admin/liora-phase7-edge/terraform`. Credentials were passed through
private process stdin/environment, never command arguments or tracked tfvars.
This state is necessary operator recovery data and is not in Git.

Ansible installed HAProxy and Certbot, validated the configuration before
replacement, enabled HAProxy and the loopback-only ACME webroot service, and
reloaded only when needed. A repeated run reached changed=0 before the later
intentional nonprod routing switch. Nonprod TLS routing stayed disabled until
its certificates and ingress were ready, then was explicitly enabled. The
private ACME service listens on `127.0.0.1:8088`; public Host names are allowlisted.
HTTP application requests redirect with 308; unknown HTTP Host returns 403.
TLS connections with unknown or administrative SNI are rejected.

The project NAT file and active table had no existing public 80/443 owners.
The helper first added only HTTP, then HTTPS after PROD certificate verification.
It preserved all 11 pre-existing forwarding rules, including VM 200 SSH and
unrelated VM 100 services, reused the existing enabled `custom77-nat.service`,
validated with `nft -c`, and created timestamped backups on the host. No complete
ruleset flush, host reboot, existing VM restart or unrelated rule deletion ran.

Backups are `/etc/nftables.d/custom77-nat.nft.liora-20261021T173152750066Z.bak`
and `.liora-20261021T173435521486Z.bak`. The first is the pre-publication file;
the second already includes HTTP and predates HTTPS. This does not establish
reboot persistence; that remains a separately scheduled check.

## Certificates, renewal and namespace delivery

PROD first passed an external ACME staging HTTP-01 challenge, then received a
trusted production certificate. DEV/STAGE production issuance succeeded after
DNS appeared. The no-email ACME registration option was explicitly selected;
no operational email address was invented. All production certificates have
explicit per-host SANs, match their private keys and expire on 2027-01-19.
The temporary staging lineage and challenge test file were removed afterward.

Each namespace has its own `app-tls` Secret. Certificates terminate at Traefik;
HAProxy performs SNI-based TCP passthrough. Certificate files were transferred
privately with key mode 0600. The TLS installer verifies the target API VIP,
namespace, SAN, validity, key match and key-file permissions, then sends Secret
data on stdin with errors suppressed. No PEM or credential value was printed.
Initial self-signed fallback responses during Secret propagation were not
counted as trusted TLS success; subsequent ordinary validation passed.

On VM 200, `liora-certificate-sync.timer` runs daily at 04:00 with up to 15 minutes
jitter and persistence across missed runs. Its service uses the existing
management SSH key and kubeconfigs to read the three fixed Certbot paths from
the edge and validate/update each namespace Secret. Only the existing management
public key was added to the edge; no SSH private key was copied. Temporary
certificate transfers are private and removed after each run. The management
account retains the template's existing sudo access; a dedicated restricted
certificate retrieval account/key remains separate hardening work.

Certbot's timer and the distribution timer are enabled. Renewal simulations
passed for all three production lineages. The real distribution service ran
successfully with `Result=success`, `ExecMainStatus=0`, updating all three Secrets;
its units passed systemd verification. This verifies each leg now, not a later
unattended real renewal cycle. No certificate archive or private key was added
to Git or to the existing version 1 recovery YAML schema.

## Application configuration and acceptance

Commit `affdd39` changes DEV's CORS/frontend origin to HTTPS and restores its
namespace TLS reference. A backend template configuration revision annotation
causes its environment to reload. DEV keeps ENVIRONMENT staging, the same image
digests, one worker and one backend/frontend replica. STAGE/PROD retain their
existing HTTPS origins; PROD keeps two backend/frontend replicas. Argo CD applied
the reviewed DEV change and completed its normal prestart hook/rollout.

The browser helper now accepts a validated IPv4 `acceptance_address` resolver
override; its existing default remains loopback. Canonical HTTPS tests mapped
each hostname to private edge `.240` inside Chromium, preserving the actual URL,
SNI, ordinary certificate validation and browser origin. All three passed:
health HTTP 200/true, UI login, item create/read/update, persistence after reload
and authenticated API read.

The operator separately confirmed from outside the private lab network:
**all three URLs load without certificate warnings**. The external web tool
could not access the URLs and is not cited as passing evidence. External HTTP
challenge validation was independently performed by the ACME authority. Public
HTTPS reachability is based on the operator's external-browser confirmation;
full automated UI/data checks used the private edge at canonical origins.

All six directed foreign-marker checks returned 404 and all six foreign-token
checks returned 403. Direct SQL found only each environment's own marker:
DEV/STAGE/PROD count vectors `[1,0,0]`, `[0,1,0]`, `[0,0,1]`. All owned markers
were removed through their owning APIs and API/SQL absence was confirmed.
An earlier PROD-only marker was also removed. No real user data was used.

Route checks confirmed trusted TLS/SAN/expiry, HTTP 308 and health 200 for all
three names. `argocd.liora.aprt.info`, `adminer.liora.aprt.info` and an unknown
SNI were rejected at the edge. The new K3s Argo CD/Adminer Services remain
private; unrelated legacy VM 100 public forwarding was intentionally preserved.
Both private Argo CD UI logins and a private DEV Adminer HTTP check were
repeated after edge publication. Temporary admin forwards were stopped.

All application workloads are Ready with zero container restarts. Existing
PVC/PV bindings are retained. DEV's backend Pod changed intentionally for the
HTTPS environment reload; other application image pins and replica counts
remain unchanged. All five Argo CD Applications are Synced/Healthy and all six
K3s nodes are Ready.

## Repository files and validation

- `edge/haproxy/terraform/main.tf`: dedicated edge VM with isolated state.
- `edge/haproxy/ansible/`: inventory, validated routing template and services.
- `edge/haproxy/liora-certificate-sync.{service,timer}` and README: distribution
  lifecycle and operator requirements.
- `scripts/proxmox/configure-liora-edge-nat.py`: guarded, backed-up NAT extension.
- `scripts/kubernetes/{install-application-tls,sync-edge-certificates}.py`:
  private certificate validation and delivery.
- `scripts/kubernetes/verify-application-ui.py`: canonical edge-address check.
- `kubernetes/apps/liora/overlays/dev/kustomization.yaml`: HTTPS origin/TLS/reload.
- `runbooks/15-publish-application.md`: end-to-end procedure, direct script links,
  renewal, publication and rollback boundaries.
- README, architecture, navigators, implementation plan and this report: current
  verified topology and scope.

Synthetic NAT checks preserved unrelated rules, tested port gating/idempotence
and rejected conflicting ownership. A generated TLS fixture verified namespace
selection, redacted output and early rejection of group-readable keys. Python,
YAML, shell and systemd syntax, Terraform validation/no-drift, HAProxy validation,
Ansible replay and all application renders passed. Gitleaks and strict offline
recovery validation passed. Recovery credentials, existing SSH private keys and
unrelated untracked documents were not rewritten or committed.

Evidence is under `/home/root-admin/liora-phase7-artifacts/`: `route-checks.json`,
`final-workloads.json`, `final-acceptance/<env>/acceptance.json`,
`final-acceptance/prod/isolation.json` and `marker-cleanup.json`. Private initial
certificate copies are in the protected local `tls/` subdirectory; live Certbot
state remains root-only on the edge. These are operator data, outside Git.

## Remaining boundaries and next phase

Phase 7 passes DNS-only public-origin HTTPS acceptance. Cloudflare proxy mode,
Full (strict) traffic, edge HA, node/edge failover, reboot
persistence, data backup/restore and a future scheduled real certificate renewal
remain unverified. Keep these limits distinct from functional acceptance.

Next after confirmation: Phase 8, separate cluster monitoring and controlled
private operational access. Do not begin Phase 8 in this increment.


## Later architecture decision

The Phase 7 limits above describe that checkpoint, not the current backlog.
The owner subsequently enabled Cloudflare protection/Access for DEV/STAGE and
removed legacy VM100 administrative DNAT. The current design retains HAProxy
and Traefik ServiceLB node pools; separate ingress VIPs are not planned. Edge
redundancy/public IP capacity is an optional future production-scale review.
See [the decision record](../../../decisions/2026-10-24-operating-model.md). This note records
owner confirmation without rerunning network tests.
