# Historical phase planning and execution notes

Archived 2026-10-25 from the implementation plan. Earlier status and
authorizations describe their original checkpoint. Use the [phase summary](../REPORT.md).

## Phase 11 — Final refinement and polishing

Status: **completed for the defined certificate and DHCP scope**, including
owner-confirmed external HTTPS checks, UptimeRobot monitoring and DHCP range
correction. Observation of the first scheduled certificate renewal remains an
operational follow-up; delegated Phase 9 work remains separate.

### Kubernetes-native certificate management

The existing pinned cert-manager 1.21.2 installation in each cluster now manages
public application certificates as well as CNPG/Barman internal TLS. Independent
`letsencrypt-cloudflare` ClusterIssuers use Let's Encrypt production ACME and
Cloudflare DNS-01. Each environment overlay owns a Certificate targeting its
existing `app-tls` Secret; no application image or database change was required.

The private token is stored in Git-ignored `recovery/cloudflare-dns-token`, mode
`0600`, with a visibly fake tracked example and a secret-safe provisioning
helper. Its required permissions are `Zone:DNS:Edit` and `Zone:Zone:Read` for
`aprt.info`. Solver selection is limited to `dev.liora.aprt.info`,
`stage.liora.aprt.info` and `liora.aprt.info`. All 60 existing DNS records were
unchanged after challenge cleanup; proxy/Access and unrelated subdomains were
not modified.

- [x] Prepare independent issuer configuration for both clusters, reusing the
      pinned controller and documenting private credential provisioning/recovery.
- [x] Migrate DEV, then STAGE, then PROD with one active TLS Secret writer.
      Disable the VM 200 distribution timer and mask its service before handover.
- [x] Verify production issuance, explicitly requested renewal to revision 2,
      trusted serving on every ingress node and HAProxy, browser login/CRUD and
      Argo ownership. CNPG/internal TLS and continuous archiving remain healthy.
- [x] Retire edge Certbot renewal and HTTP-01 webroot operation, preserve private
      rollback state/scripts, and update deployment/recovery documentation.

Evidence and limitations are in [Phase 11](certificate-migration-2026-10-24.md). All five Argo
Applications are Synced/Healthy with successful operations and their existing
automated policies. The owner subsequently confirmed external browser access
without certificate warnings for all three domains. The supplied external
OpenSSL results show the new certificate validity dates and fingerprints,
matching the expected renewal expiry timestamps. This resolves the external
verification gap; the execution host's earlier connection refusal is historical.

UptimeRobot monitors availability and certificates for `liora.aprt.info`,
`dev.liora.aprt.info` and `stage.liora.aprt.info`, as confirmed by the owner.
An additional internal certificate-expiry integration was not required to close
that checkpoint. It was subsequently added by the separately authorized alerting
hardening below, complementing UptimeRobot. Real certificate-failure delivery
was not induced; threshold, routing and transport checks are recorded separately.

- [x] Obtain external verification of all three application HTTPS domains.
- [x] Confirm external availability and certificate monitoring through UptimeRobot.
- [ ] Observe the first scheduled unattended certificate renewal when due.
      Manual renewal through the same controller/ACME/Secret path has passed.

DNS-01 removes the public HTTP challenge-path dependency. The owner now
confirms Cloudflare protection/Access enabled for DEV/STAGE and removal of
legacy VM100 administrative DNAT. The certificate migration itself did not
perform those owner-managed changes; no fresh Access or NAT test is claimed
by this documentation update.

### Subsequent alerting hardening — 2026-10-24

- [x] Review all 55 previously loaded definitions and fix coordinator namespace
      ingestion and direct-event fingerprint identity without changing backups.
- [x] Add capacity/accounting, scheduling, notification and public-certificate
      diagnostics using existing metrics; retain independent critical signals.
- [x] Deploy NONPROD then PROD; verify 81 rules, 60 healthy targets, no pending/
      firing conditions, preserved Secret/PVC identities and unchanged timer.
- [x] Record source/live audit commands, fixture/routing tests, results and further
      proposals in [the hardening report](../../../evidence/records/2026-10-24-alerting-optimization.md).

These alerting checks do not complete delegated Phase 9 work or replace monthly
PITR. Before another Terraform apply, compare the current VM memory fix/private
overrides with the tracked 2048 MiB minimum default; VM policy was not changed
by alerting work. The owner confirmed receipt of all three post-rollout backup
telemetry RESOLVED messages; timestamps are recorded in the hardening report.

### DHCP and static address alignment

The owner corrected the Proxmox DHCP range to `192.168.77.180`–
`192.168.77.199`. Existing machines use static addresses; DHCP remains enabled
for onboarding new machines. The old `.201`–`.241` overlap is resolved.

- [x] Retain DHCP for initial configuration of new machines and use a range
      separate from the documented static VM addresses and API/Admin VIPs.
- [x] Record the owner-applied DHCP correction to `.180`–`.199`. This update
      records operator confirmation; no DHCP configuration was changed or
      independently inspected during the documentation update.

**Pass:** public application certificate issuance and renewal use per-cluster
cert-manager with Cloudflare DNS-01, superseded certificate automation is
retired, and the documented DHCP allocation no longer overlaps static addresses.

### Early PVC filesystem and PROD replication alerts — 2026-10-24

- [x] Add node-grouped local-path byte/inode headroom and mounted-PVC telemetry
      alerts using canonical kubelet metrics, without treating requests as quotas.
- [x] Add PROD standby/streaming, replay-lag and replication-query telemetry
      alerts; retain asynchronous replication and existing database placement.
- [x] Validate local regression/routing fixtures; deploy NONPROD then PROD and
      verify 95 healthy rules, 60 healthy targets, no active/pending conditions,
      matching source/live rules/inhibition and preserved protected identities.
- [x] Document thresholds, response procedures, limitations and actual results in
      [the follow-up report](../../../evidence/records/2026-10-24-storage-replication-alerts.md) and
      [operator guidance](../../../../operations/STORAGE_REPLICATION_ALERTS.md).

This completes item 2 of the alerting hardening report's proposed improvements.
It does not replace PITR verification or complete pending Phase 9 work.
