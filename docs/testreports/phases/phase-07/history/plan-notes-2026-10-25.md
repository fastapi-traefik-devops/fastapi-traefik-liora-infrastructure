# Historical phase planning and execution notes

Archived 2026-10-25 from the implementation plan. Earlier status and
authorizations describe their original checkpoint. Use the [phase summary](../REPORT.md).

## Phase 7 — Publish the application

Status on 2026-10-21: **complete for direct DNS-only origin access**. See
[Phase 7 report](../REPORT.md). The three real domains resolve to the public
Proxmox origin. VM 240 at `192.168.77.240` runs application-only HAProxy routing;
public 80/443 DNAT preserves the existing SSH and unrelated host rules. Distinct
node ingress pools reuse ServiceLB rather than the API VIPs or new floating VIPs.

Trusted per-host certificates are installed in each app namespace. DEV now uses
HTTPS CORS/origin and its backend was rolled to load the new environment.
Canonical HTTPS browser login/item persistence and mutual API/SQL/token isolation
passed for all three environments. The operator independently confirmed all three
URLs load externally without certificate warnings. Test items were removed.
Certbot renewal simulations and the management certificate-distribution service
passed; both timers are enabled. Argo CD remains Synced/Healthy.

Cloudflare currently supplies DNS only: proxied traffic and Full (strict) mode
were not configured or verified at that checkpoint. Later decisions retain
HAProxy and its node pools without dedicated ingress VIPs; owner-confirmed
Cloudflare Access and legacy DNAT cleanup are recorded in the decision update.
Edge failover,
reboot persistence and a later unattended renewal cycle remain untested.
Phase 8 progress is recorded below.

- [x] Configure real DEV, STAGE, and PROD hostnames, DNS, ingress, and TLS.
      Replace `*.example.com`; align backend CORS and frontend settings.
- [x] Establish distinct ingress addresses and edge routing. Current kube-vip
      covers the **API VIPs only** and K3s ServiceLB is enabled. Decide ingress
      addressing before adding HAProxy and Proxmox TCP/443 DNAT.
- [x] Verify each hostname reaches only its intended environment and that
      valid TLS, UI login, and the API work.

**Pass:** the application works at its real URLs. Keep Argo CD, Adminer, and
other admin interfaces behind Tailscale or equivalent private access.
