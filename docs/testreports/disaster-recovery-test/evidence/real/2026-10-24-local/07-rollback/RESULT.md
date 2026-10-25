# Test 7 — PASS: real local workload and PostgreSQL logical rollback

Actual run 24 October 2026, 10:13:31 Europe/Tirane, 36.926s total.
Workload HTTP response v1 → v2 → v1 after real kubectl rollout undo.
Measured workload rollback including verification: 2.204s.
The original PVC marker liora-dr-20261024 survived cluster stop/start and both rollouts.

Fresh synthetic CNPG PostgreSQL 16.15 resumed from its retained 2Gi PVC.
pg_dump captured a real custom-format checkpoint of public.dr_checkpoint.
After update/insert, pg_restore --clean --if-exists restored that test table.
Before: 1|checkpoint-v1. Changed: 1|changed-v2 plus 2|after-checkpoint.
After rollback: exactly 1|checkpoint-v1, independently asserted by the runner.
Logical rollback including verification: 0.602s.
Database Ready, original PVC Bound, plpgsql and uuid-ossp extensions verified.

First attempt failed because Alpine lacked httpd. first-failure.log and first-run.log
retain the error/90s rollout timeout. Switching only the disposable HTTP fixture
image to BusyBox 1.37 fixed it. Every executed command and exit code is retained
in rollback.log. Focused log-viewer screenshots are labeled as recorded output.

This is a real Kubernetes workload rollback and a real PostgreSQL logical table
checkpoint restoration, using synthetic local data. The HTTP workload is a
BusyBox fixture, not recovered Liora. This is NOT WAL replay, PITR, an R2 restore,
full database recovery, original data integrity verification or Proxmox DR.
