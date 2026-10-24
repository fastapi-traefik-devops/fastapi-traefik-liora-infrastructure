# Phase 11 — Public certificate migration

Status: **preparation started; live cutover blocked on the DNS API credential**.
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

## Pending execution

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

No claim of completed migration or renewal verification is made.
