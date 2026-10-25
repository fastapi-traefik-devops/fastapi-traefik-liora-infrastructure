# Evidence index

Evidence records a specific date, environment and method. It is not proof of
current health. Keep failed and blocked results with successful results.
Private logs, credentials and recovery inputs stay outside Git.
Follow the [documentation rules](../../docs-structure.md).

| Date | Environment / method | Record | Establishes |
| --- | --- | --- | --- |
| 2026-10-23 | NONPROD and PROD / live dashboard checks | [Grafana screenshots and JSON](grafana-operations/README.md) | Dashboard queries and rendering at capture time; includes active telemetry alerts. |
| 2026-10-24 | Local fixtures and simulations | [Original DR assessment](records/disaster-recovery-test-report.md) | Local software checks; full infrastructure recovery blocked. |
| 2026-10-24 | Disposable local Kubernetes/runtime | [DR follow-up package](../disaster-recovery-test/README.md#independent-local-runtime-follow-up--24-october-2026) | Limited local recovery checks; R2 and complete application recovery blocked. |
| 2026-10-21–25 | Per-record scope | [Implementation records](records/README.md) | Changes, recorded checks and remaining work; distinguish local tests from live execution. |

The DR package retains its original paths, checksums, provenance and scripts.
Its indexes separate simulated panels from real output. Do not run historical
generators in place: they can overwrite the saved record and emit old paths.

Checksum manifests cover the current published package. During this reorganization,
only Markdown cross-references and their checksum entries changed; raw results,
screenshots, source provenance and executable snapshots retain their bytes.
