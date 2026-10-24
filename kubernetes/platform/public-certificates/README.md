# Public application certificates

This is the Phase 11 DNS-01 configuration. HAProxy continues TLS passthrough;
Traefik terminates TLS using each application's existing `app-tls` Secret.
The installed cert-manager version remains pinned in `../cert-manager`.

**Activation is pending.** The current cert-manager is limited to CNPG internal
certificates. Do not apply these Certificate resources while the legacy
distribution helper can still write the same Secrets.

## Private DNS credential

Create `recovery/cloudflare-dns-token` containing only a Cloudflare API token,
with file mode `0600`. This path is Git-ignored; the adjacent `.example` is
deliberately fake. Include the real file in the encrypted private recovery kit.
Use `Zone:DNS:Edit` and `Zone:Zone:Read`, restricted to the `aprt.info` zone.
The R2 bucket credential is a separate credential and is not reused.

Validate without changing clusters:

```sh
python3 scripts/kubernetes/bootstrap-cloudflare-dns.py
```

After validation, provision the token separately in the selected cluster:

```sh
python3 scripts/kubernetes/bootstrap-cloudflare-dns.py --apply --cluster nonprod
```

[Standalone credential helper](../../../scripts/kubernetes/bootstrap-cloudflare-dns.py)

The helper checks the expected API VIP and sends Secret data through stdin,
without a last-applied annotation. Errors print exception types, never API
responses or token values. Zone visibility does not prove DNS edit permission;
the actual DNS-01 challenge must demonstrate that permission.

## Required cutover order

1. Extend the existing cert-manager installation to watch application namespaces
   and enable ACME, Order and Challenge controllers; preserve CNPG internal TLS.
2. Provision the private token in `cert-manager` and apply `issuer.yaml`
   independently in each cluster. Each cluster owns its own ACME account key.
3. Save existing `app-tls` Secrets to private recovery storage. Stop and disable
   VM 200's distribution timer, confirm no distribution service is running, and
   prevent manual use of the legacy helper during the migration.
4. Migrate DEV, then STAGE, then PROD. Manage each matching Certificate through
   its application overlay and allow Certificate resources in the Argo project.
   Keep the existing TLS Secret available throughout issuance.
5. Check DNS-01 completion, Certificate Ready, validity/SANs, the certificate
   actually served by every Traefik endpoint and normal HTTPS application access.
   Request and observe a renewal before retiring the corresponding legacy issuer.
   Verify CNPG/plugin TLS and backups remain healthy after extending cert-manager.
6. Only after all three environments pass, disable legacy Certbot renewal and
   remove the HTTP-01 webroot dependency from the HAProxy configuration. Preserve
   private Certbot state and the rollback procedure; retain historical helpers.

If a checkpoint fails, stop advancing environments. Keep the last working TLS
Secret. Before restoring a legacy writer, suspend the matching Certificate
reconciler/ownership deliberately so two writers cannot compete. Do not delete
working TLS Secrets as a recovery shortcut.

This directory currently contains preparation, not evidence that issuance,
renewal or migration has succeeded. See the Phase 11 report for execution state.
