# Phase 11 — Certificates and refinement

Summary as of 2026-10-25. Environment: NONPROD and PROD; three application domains.

## Result

The defined public-certificate and DHCP scope is complete in the saved record.

| Area | Recorded verification |
| --- | --- |
| cert-manager DNS-01 | Issuance, requested renewal to revision 2, trusted node/edge serving and application checks passed on 2026-10-24. |
| External HTTPS | Owner-confirmed browser checks and supplied OpenSSL output resolved the execution host's external-access gap. |
| External monitoring | Owner confirmed UptimeRobot availability and certificate monitoring. |
| DHCP | Owner confirmed `.180`–`.199`, separate from static VM and VIP addresses. No independent DHCP inspection is claimed. |
| Alert hardening | Later 2026-10-24 records report 95 healthy rules and 60 healthy targets after storage/replication additions. |

## Remaining verification

- Observe the first scheduled unattended certificate renewal when due.
- Continue monthly PITR and the separate recovery work in the [active plan](../../IMPLEMENTATION_PLAN.md).

Requested renewal proves the controller path, not a future unattended renewal.
Saved monitoring counts do not establish current health or tested failover.

## Records and procedures

- [Certificate execution, owner confirmations and evidence](history/certificate-migration-2026-10-24.md)
- [Former plan and execution notes](history/plan-notes-2026-10-25.md)
- [Alert hardening](../../evidence/records/2026-10-24-alerting-optimization.md)
- [Storage and replication verification](../../evidence/records/2026-10-24-storage-replication-alerts.md)
- [Certificate procedure](../../../../runbooks/15-publish-application.md)
