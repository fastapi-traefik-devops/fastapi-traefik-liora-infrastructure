# Phase 11 — Public certificate migration

Status: **public certificate migration completed on 2026-10-24**, with the
external network and future unattended-renewal limitations recorded below.
This report covers the public certificate subtask only. DHCP alignment and other
polishing work are outside this checkpoint.

## Preflight on 2026-10-24

Infrastructure started at `8ff119f`. The application checkout was clean.
An existing `docs/testreports/.IMPLEMENTATION_PLAN.md.swp` was preserved; the
plan itself was not edited while that operator editor artifact was present.

Both clusters already have pinned cert-manager 1.21.2 from Phase 10.2. The
NONPROD controller has an available replica and is restricted to `cnpg-system`,
with only self-signed certificate/issuer controllers enabled. Extending its
scope and enabling ACME is required, rather than installing a second controller.

VM 200's `liora-certificate-sync.timer` is enabled and its service was inactive
at inspection. VM 240's `certbot.timer` is enabled and HAProxy is active.
No live settings, Secrets, application images, databases or automation were
changed. The existing certificate writers remain responsible for renewal.

Documented recovery inputs contain R2 credentials, but no DNS API token was
found there. The R2 credential was not reused. A zone-scoped DNS token was
requested through a private file, without requesting its value in chat.

## Prepared locally

- Independent per-cluster ACME ClusterIssuer configuration using Cloudflare
  DNS-01, plus three separate environment Certificate manifests targeting the
  existing namespace-local `app-tls` Secrets.
- A standalone credential bootstrap helper that checks private file permissions,
  zone visibility and the destination API VIP; applies Secret data through stdin;
  and withholds API response bodies and token values from diagnostics.
- A visibly fake example and a Git ignore for the documented token file.
- An explicit staged activation outline, preserving CNPG internal TLS and
  keeping legacy writers active until the coordinated handover.

Four local tests passed: exact per-environment certificate scope, secret-safe
error output, private regular-file requirements and stdin-only provisioning
with cluster endpoint checks. The issuer Kustomize render and `git diff --check`
passed. These checks do not prove live DNS permission, issuance or renewal.

## Original execution checklist

1. Obtain and verify the private Cloudflare token scoped to `aprt.info`.
2. Extend the existing cert-manager configuration, preserve internal plugin TLS,
   and provision the independent cluster issuer/token configuration.
3. Coordinate a single writer for `app-tls`, integrate the corresponding Argo
   permissions/overlays, then migrate DEV, STAGE and PROD sequentially.
4. Verify initial issuance, renewal, served certificates and application access;
   retain diagnostic evidence and verify CNPG/plugin health.
5. Retire legacy renewal/distribution and HTTP-01 webroot dependencies only after
   all checkpoints pass. Preserve private renewal state and historical helpers.
6. Update the implementation plan, permanent deployment/recovery instructions
   and edge configuration to the actual completed implementation.

This preparation checklist was subsequently completed as recorded below. The
initial blocked state above is retained as execution history.


## Execution and ownership handover

The supplied DNS credential was saved privately at
`recovery/cloudflare-dns-token` with mode `0600`; the original supplied text was
also restricted to `0600`. No values were printed, tracked or pushed. Zone read
access and actual DNS-01 presentation/cleanup succeeded. No token permissions,
branch rules, application DNS routing records, proxy settings or Access rules
were changed. The R2 token was not reused.

Both existing cert-manager 1.21.2 installations retained their image digests and
50m CPU/64Mi requests, 500m/256Mi limits. Removing the controller namespace and
controller-list restrictions enabled the default ACME/Order/Challenge controllers
while keeping self-signed CNPG internal certificates. Each cluster independently
registered `letsencrypt-cloudflare`; each keeps its own account key in
`cert-manager/letsencrypt-cloudflare-account`. Only the three exact application
names match the solver. No wildcard or zone-wide Certificate was introduced.

Before the first Certificate was created, the VM 200 distribution timer was
disabled. Masking its locally installed service initially required preserving
its existing unit as
`/etc/systemd/system/liora-certificate-sync.service.phase11-disabled`; the
replacement is now masked and inactive. No distribution process was running.
The private directory `.local-work/private/phase11/` contains the DNS snapshot
and pre-cutover TLS Secret backups. These contain private operator data and
must remain outside Git.

DEV, STAGE and PROD were issued sequentially, then each was manually renewed
with checksum-verified cmctl 2.6.1. Normal DNS propagation required more than a
60-second initial wait for some environments; bounded waits were repeated with
the same healthy outstanding request. No working Secret was deleted. Renewal
reached revision 2 with a changed serial and leaf fingerprint in every case.
All certificates expire on 2027-01-22; their scheduled renewal timestamps are:

| Environment | Final revision | Scheduled renewal UTC | Final leaf SHA-256 |
| --- | --- | --- | --- |
| DEV | 2 | 2026-12-23 07:46:02 | `3a0f770e7d74c62aab60e83b91f5a62340a2230dc1e27371dcf53877fad59149` |
| STAGE | 2 | 2026-12-23 07:48:41 | `f8693eb90b0941f6359e1350922fced6b7f74ecdfd11e067602000833c122577` |
| PROD | 2 | 2026-12-23 07:52:27 | `0dcb2230cc31edff221e7f0c7b7003c321bb45b43dcb30a01b3f00f292a4afde` |

Normal OS trust and exact leaf equality against the namespace Secret passed on
each of the three respective cluster node addresses and HAProxy `.240` for
every hostname. Browser login and disposable item create/read/update/reload/
delete passed through the private edge for all three environments. The first
browser invocation lacked the extracted system-library path; using the existing
`scripts/local-python.sh` wrapper resolved that local tooling failure.

Argo projects now permit namespaced Certificate resources and each application
overlay includes its own Certificate. All three resources have matching Argo
tracking IDs. All five Applications reached Synced/Healthy with Succeeded
operations; automated policies were preserved, including PROD no-prune.
Certificate changes did not modify any environment's image digest pair. Browser
checks used the existing application images; this task did not trigger a Jenkins
build.

## Legacy retirement and preservation

The reviewed HAProxy template was applied with the existing Ansible on VM 200,
after syntax check, check-mode diff review and preservation of the original
configuration. Only operator playbook/inventory/template files were transferred;
no additional repository checkout was created. HAProxy validated and reloaded
successfully. TLS passthrough and backend node sets stayed the same. Known HTTP
hosts, including the former challenge path, return 308; an unknown Host returns
403. No Proxmox NAT changes were made.

VM 240 had only the three project Certbot renewal configurations. Its
`certbot.timer` and `liora-acme-webroot.service` are now disabled and inactive;
HAProxy remains active. Root-only `/etc/letsencrypt`, the old unit files/webroot,
private TLS rollback copies, and tracked distribution/installer scripts remain
preserved. Fresh provisioning no longer installs Certbot or starts the webroot.
Fresh deployment/recovery uses runbook 15 and does not install distribution units.

Restoring a legacy writer is not an automatic rollback: first hold the affected
Argo child and its root declaratively, prevent the matching Certificate from
being recreated, and ensure it cannot update the Secret. Before removing a
Certificate, inspect Secret ownerReferences and preserve the Secret explicitly;
never let cascading deletion destroy a working TLS Secret. Restore the selected
private TLS backup only after that single-writer boundary is established. The
saved VM 200 unit can then replace the mask if a deliberate legacy rollback is
required. This rollback was retained but was not executed.

## Regression checks and evidence

- Cloudflare before/after snapshots contained the same 60 existing records;
  zero unexpected record changes and zero remaining project challenge records.
- Both clusters' Barman client/server Certificates remain Ready. All database
  Clusters remain Ready with ContinuousArchiving=True and LastBackupSucceeded=True.
  A read-only `pg_stat_archiver` check showed zero failures and recent successful
  archives in all three environments. No database Pods or application data were
  replaced for this task; Jenkins state and private recovery inputs were untouched
  except for adding the DNS credential and private certificate rollback evidence.
- Six certificate/credential tests and five CNPG/deployment tests passed. The
  render splitter now accepts Certificate/ObjectStore resources and places the
  ObjectStore before the Cluster. Its inline operator copy was updated too.
- The pinned cmctl installer checksum/idempotence and shell syntax checks passed;
  manifest rendering, Ansible syntax/check-mode/apply and staged diff checks passed.
  Exact token matching found no credential in tracked files.
- Existing application commits and shared infrastructure history were preserved.
  Concurrent observer/recovery work was merged with `e4505e9`; later independent
  Jenkins changes were merged with `943baff`, without modifying their contents.
  No Jenkins job, polling or scheduling setting was changed by this certificate task.

Implementation commits: `2c1617d` (preparation), `c882023` (cluster-local TLS),
`b70bec0` (manual deployment compatibility), `55f6085` (edge dependencies).
The reviewed implementation was pushed normally to main at `943baff`.

Private evidence remains under `.local-work/private/phase11/`: initial/renewed/
final TLS JSON, per-environment browser acceptance JSON, `dns-before.json`,
`dns-audit.json`, `platform-checks.json`, `archive-status.json`, the old edge
configuration and pre-cutover TLS Secret backups. Do not publish that directory.

## Remaining boundaries

Public-DNS TCP access from this execution host returned ConnectionRefusedError;
private node and edge checks passed with real hostnames and normal certificate
validation. A new independent external-browser confirmation remains outstanding.
The helper's explicit `--public` mode preserves that distinction. No public
reachability result is inferred from DNS-01 issuance.

Manual renewal verified the same controller/ACME/Secret update path used for
scheduled renewal, but the future unattended renewal date has not yet occurred.
Dedicated public-certificate expiry alert integration was not added. DHCP/static
alignment and the remaining Phase 9 work are still separate pending tasks.
