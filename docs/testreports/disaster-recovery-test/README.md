# Disaster recovery test evidence

Start with [the report](../evidence/records/disaster-recovery-test-report.md) and the
[evidence index](evidence/INDEX.md).

These artifacts record the 24 October 2026 assessment/exercise. **No real
infrastructure recovery was executed.** The 15 infrastructure tests are BLOCKED;
their illustrative screenshots say **SIMULATED — NOT A REAL TEST**.
Actual local software checks and read-only live observations are under
`evidence/real/`. Local test success is not a production recovery PASS.

The report, logs and screenshots are historical output. The repository revisions
in `repository-provenance.json` describe the original source checkouts, before
this evidence was added to the infrastructure repository.

## Retained sources

- `run_local_tests.py`: disposable JSON/SQLite simulations, cleanup guards,
  offline repository Jenkins archive fixtures, and static ArgoCD YAML assertions.
  Uses existing Python and PyYAML; it never contacts infrastructure.
- `test_local_https.py`: actual loopback Python/SQLite fixture, generated test
  certificates, TLS/Host checks, rollback and cleanup. Requires existing
  `cryptography`; it is not FastAPI, PostgreSQL or HAProxy.
- `render_evidence.py`: screenshots of labeled local HTML panels using an existing
  Chrome installation and a disposable browser profile. It installs nothing.
- `capture_readonly.py`: historical metadata collector using the original
  operator's `Liora` SSH alias and identity. It performs GET queries only. It is
  operator-specific and is not required to read or verify the saved evidence.
- `finalize_report.py`: regenerates the report/index from saved results. It does
  not contact infrastructure, but overwrites generated artifacts.

Rerunning generators replaces historical output. Preserve this committed record
before any separately reviewed repeat. No credentials, recovery archives,
Terraform state or production database data are included.

Verify artifact integrity from the infrastructure repository root:

```sh
sha256sum -c docs/testreports/disaster-recovery-test/evidence/SHA256SUMS
```


## Independent local runtime follow-up — 24 October 2026

The preceding assessment is preserved as historical evidence. A subsequent actual
local runtime exercise is documented separately:

- [Independent audit and improvements](DR_INDEPENDENT_AUDIT_REPORT.md)
- [Real local recovery report](LOCAL_DISASTER_RECOVERY_TEST_REPORT.md)
- [Presentation-ready selections](DR_PRESENTATION_FINAL_EVIDENCE.md)
- [New evidence index](astra-review/INDEX.md)
- [Verifier and validation instructions](astra-review/README.md)

25 captures yielded 24 unique genuine screenshots; one exact duplicate is not
republished. Local Kubernetes storage, limited Argo/monitoring, synthetic Jenkins
restore and logical/workload rollback passed. **R2 restore and complete application
recovery remain blocked.** These results do not supersede historical simulations
or prove full Proxmox disaster recovery.

## Archive maintenance

The [documentation rules](../../docs-structure.md) govern new records.
Recorded generators retain their original report names and source paths.
They are historical executable snapshots, not documentation maintenance tools.
The [reports index](../README.md) locates moved phase records.
