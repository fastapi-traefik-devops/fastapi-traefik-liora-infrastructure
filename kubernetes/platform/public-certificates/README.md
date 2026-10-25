# Public application certificates

HAProxy passes TLS through to Traefik. Each environment overlay includes a
Certificate that owns its existing namespace-local `app-tls` Secret. The shared
pinned cert-manager installation handles both public ACME certificates and
CNPG/Barman internal TLS. Its default controllers watch all namespaces.

`issuer.yaml` is installed independently in both clusters. Each cluster registers
its own ACME account and stores its own account key. The Cloudflare DNS-01
solver selects only `dev.liora.aprt.info`, `stage.liora.aprt.info` and
`liora.aprt.info`. It creates/removes their `_acme-challenge` TXT records without
changing application routing records or unrelated subdomains.

Keep the zone-scoped DNS token in Git-ignored `recovery/cloudflare-dns-token`,
mode `0600`, and include it in the encrypted recovery kit. The adjacent tracked
example is deliberately fake. The token needs `Zone:DNS:Edit` and
`Zone:Zone:Read` for `aprt.info`; do not reuse R2 credentials.

Use [runbook 15](../../../runbooks/15-publish-application.md) for fresh setup,
credential provisioning, certificate verification, renewal and troubleshooting.
[The standalone credential helper](../../../scripts/kubernetes/bootstrap-cloudflare-dns.py)
checks file permissions, zone visibility and the intended cluster API VIP.
Errors withhold token values and API response bodies. Actual DNS-01 issuance
verifies DNS write permission.

The one-time Certbot handover and its private rollback artifacts are recorded in
[the Phase 11 report](../../../docs/testreports/phases/phase-11/history/certificate-migration-2026-10-24.md). The retained
legacy synchronization helpers are not part of fresh deployment or recovery.
