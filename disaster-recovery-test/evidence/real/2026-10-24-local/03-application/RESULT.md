# Test 3 — BLOCKED: real pinned application recovery

The actual pinned DEV frontend/backend images were requested in the isolated
namespace dr-application. Both GHCR pulls returned HTTP 401 Unauthorized.
See events.log. Failed application Deployments were scaled to zero.

No registry credential was available in the lab, and no original Kubernetes
cluster was queried to obtain one. The older cached backend/frontend images are
from August and do not match pinned release digests, so they were not presented
as recovery of the documented release.

A new synthetic CNPG PostgreSQL database was attempted with generated credentials
for a later independent local rollback test. This is initdb, not a restored R2
backup. Migrations/login/authentication/CRUD/application persistence were NOT
verified. No production migrations or application connections occurred.

A first over-broad lab egress policy also blocked CNPG API access. The policy was
narrowed to application pods; database access to its local API was restored.

The fresh PostgreSQL 16.15 cluster reached Ready and was hibernated to release
RAM before Argo CD. Its PVC remains Bound. startup.log says backend/frontend
"successfully rolled out" after they had been scaled to zero; that message does
NOT prove either application ran. events.log records the actual 401 failures.
