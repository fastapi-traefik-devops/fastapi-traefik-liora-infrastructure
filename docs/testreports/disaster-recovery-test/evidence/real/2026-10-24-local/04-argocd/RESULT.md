# Test 4 — PASS within local scope: Argo CD and manual GitOps sync

Argo CD 3.5.6 restored from the repository's pinned upstream commit.
Core server, repo server, Redis and application controller became Ready.
Dex, notifications and ApplicationSet controllers remained at zero replicas.
Two actual DEV/STAGE Application definitions were adapted to dr-gitops with
skip-reconcile=true, automation disabled and a project permitting only the local API.
They were accepted, but full DEV/STAGE workloads were intentionally not synced.

A separate AppProject allowed only ConfigMaps in dr-gitops from the disposable
local Git server. Actual Argo reconciliation synced recovered-backend-config,
using sanitized data derived from the original backend ConfigMap.
Operation Succeeded, resource Synced, application Healthy, commit
6f94205198d0b93745144059e363673df78a33a6.
Operation timestamp 08:01:14 UTC → 08:01:14 UTC (under one second at recorded
one-second resolution). Total installation started 09:58:39 Europe/Tirane;
core installation/held definitions completed about 10:00:04.
Node measured 1.368 GiB under a temporary 2 GiB cap.

First static-HTTP Git attempt failed with unexpected EOF; retained in sync.log
and 01-applications-ui.jpg. Switching to a lab-bridge read-only Git daemon fixed it.
See sync-retry.log and the actual Argo UI screenshots.
Anonymous UI access was read-only and reachable only through loopback forwarding.
No production cluster credentials or destination were registered.

This proves local controller startup, adapted GitOps object acceptance and a
real ConfigMap sync. It does not prove full application restore, preserved Argo
history/SSO/secrets, or restoration of original controller persistent state.
