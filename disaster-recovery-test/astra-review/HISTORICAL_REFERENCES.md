# Historical sources, not new execution evidence

The original 24 October simulation/fixture assessment remains in
[the historical index](../evidence/INDEX.md) and
[its original report](../../DISASTER_RECOVERY_TEST_REPORT.md).
The ten simulated screenshots remain explicitly labeled in their original location.

The [Phase 10.2 report](../../docs/testreports/PHASE10_2_REPORT.md) describes
23 October DEV/STAGE/PROD PITR: 286.163s / 195.483s / 287.029s. These are historical
claims, exclude infrastructure reconstruction, and were not rerun locally.
The [NONPROD assurance image](../../docs/operations/screenshots/grafana-operations/nonprod-assurance.png)
shows an older NOT INSTRUMENTED backup panel; the
[PROD operations image](../../docs/operations/screenshots/grafana-operations/prod-operations.png)
shows one critical alert. Neither establishes a new successful recovery.

Source reviewed at ff154ae7a81858f5dcdf49d0582cb1d1074a6943. Existing copies
are linked in place to avoid redundant binaries; their original bytes are preserved.
