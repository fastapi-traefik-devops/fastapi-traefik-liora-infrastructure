# Historical sources, not new execution evidence

The original 24 October simulation/fixture assessment remains in
[the historical index](../evidence/INDEX.md) and
[its original report](../../evidence/records/disaster-recovery-test-report.md).
The ten simulated screenshots remain explicitly labeled in their original location.

The [Phase 10.2 report](../../phases/phase-10/history/r2-backup-pitr-2026-10-23.md) describes
23 October DEV/STAGE/PROD PITR: 286.163s / 195.483s / 287.029s. These are historical
claims, exclude infrastructure reconstruction, and were not rerun locally.
The [NONPROD assurance image](../../evidence/grafana-operations/nonprod-assurance.png)
shows an older NOT INSTRUMENTED backup panel; the
[PROD operations image](../../evidence/grafana-operations/prod-operations.png)
shows one critical alert. Neither establishes a new successful recovery.

Source reviewed at ff154ae7a81858f5dcdf49d0582cb1d1074a6943. Existing copies
are linked in place to avoid redundant binaries; their original bytes are preserved.
