# Test 2 — PARTIAL: pinned dependencies ready; R2 restore BLOCKED

24 October 2026, approximately 09:51–09:54 Europe/Tirane.
CNPG 1.30.1, cert-manager 1.21.2 and Barman Cloud Plugin 0.15.1 installed
from repository manifests with unchanged pinned OCI digests into the local lab.
See operator-install.log and dependencies.log for real rollouts and certificates.

No protected physical backup copy, WAL set, or independently verified read-only
R2 identity is available. The user confirmed no such local inputs are held.
The existing report describes a writer/delete identity, unsuitable for this lab.
No R2 credentials were imported, no ObjectStore was created and no original
archive was accessed. Therefore no restored schema/users/data/PITR result exists.

Historical DEV backup IDs in Phase 10.2 are documentary references, not independently
verified available backups today: 20261023T135047 (PITR), 20261023T154448 (full cycle).
The old source-dependent pitr.py was not run because it writes live markers and
queries original Kubernetes environments.

The dependency startup proves installability on this local node, not R2 recovery.
A later application fallback may use a fresh synthetic local database, clearly
separate from any recovered DEV data.
