# Phase 10.2 — R2 physical backups and isolated PITR

Status: **in progress; backup/recovery readiness not yet established**.

Starting infrastructure main `14d73d0` is clean and includes intervening Slack
routing and Phase 9 helper-pin work; preserve these commits. Both original
checkouts are used. Current CNPG 1.30.1/PostgreSQL 16.15 databases are healthy
and existing application data is now protected. Argo starts Synced/Healthy.

Supplied credentials were imported into ignored recovery YAML, with private
file modes and no value output. Token verification succeeded; metadata reads
for policy/bucket/public access/lifecycle return 403. No permissions were changed.
The owner confirms an empty dedicated bucket. S3 access checks are separate
from metadata-policy verification.

VM 250 is reachable as root-admin, Tailscale is active and IPv4 forwarding is
1. Preserve its existing routing. No backup timer existed at inspection.

Latest operator steering delegates Slack setup/delivery to another person.
This checkpoint integrates Alertmanager only; Slack receipt is not claimed.

Implementation and measured restore results will be recorded below. Phase 9
features, application builds/publication and public certificates are outside
this checkpoint. PROD image promotion remains gated separately.
