# Decision records

Desired design: [architecture](../../ARCHITECTURE.md).
Maintenance: [documentation rules](../../docs-structure.md).

| Record | Status and scope |
| --- | --- |
| [2026-10-24 operating model](2026-10-24-operating-model.md) | Accepted: edge/node-pool ingress, private Secret provisioning and PROD Adminer. Supersedes conflicting earlier targets. |
| [Admin VIP status ownership](admin-vip-status-ownership.md) | Accepted in Phase 8 (2026-10-22): admission guard prevents competing Service status writes. |
| [Cilium alternative](cilium-alternative.md) | Historical alternative; not selected. Flannel and the embedded policy controller remain the design. |

Earlier proposals remain in phase histories. They do not override the accepted
architecture. Link a future superseding decision in both records.
