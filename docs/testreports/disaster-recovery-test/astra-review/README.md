# Independent local DR review

[Audit](../DR_INDEPENDENT_AUDIT_REPORT.md) · [Evidence index](INDEX.md) ·
[Runtime report](../LOCAL_DISASTER_RECOVERY_TEST_REPORT.md) ·
[Presentation selections](../DR_PRESENTATION_FINAL_EVIDENCE.md)

This directory name is an organizational label, not a claim of a separate model
or third-party auditor. The review evaluates the saved run and adds local checks.

- `screenshots/`: 24 unique genuine images from 25 captures, organized by component.
- `../evidence/real/2026-10-24-local/`: sanitized original logs, API data and outcomes.
- `recorded-scripts/`: selected original one-off implementations; read their README before reuse.
- `scripts/`: improved guarded verifier, regression tests and publication validator.
- `test-results/`: additional audit validation logs and stopped-lab recheck.
- `source-provenance.json`: source revisions, source file times/hashes, published hashes and duplicate mapping.

Run from the infrastructure repository root with Python 3.10+ and Pillow/PyYAML
for package validation (the read-only verifier itself uses only the standard library):

```sh
python3 -B docs/testreports/disaster-recovery-test/astra-review/scripts/test_verify_local_lab.py
python3 -B docs/testreports/disaster-recovery-test/astra-review/scripts/validate_package.py
sha256sum -c docs/testreports/disaster-recovery-test/evidence/SHA256SUMS
sha256sum -c docs/testreports/disaster-recovery-test/astra-review/SHA256SUMS
```

Optional actual retained-lab read-only recheck, requiring Docker/kubectl access:

```sh
python3 -B docs/testreports/disaster-recovery-test/astra-review/scripts/verify_local_lab.py \
  --mode stopped --output /tmp/liora-dr-new-recheck
```

Use a new output path each time. `--mode running` requires the original exact
lab UID and active dependencies/storage workload; the retained lab is stopped,
and this verifier does not start it. It does not verify R2/application recovery.

Historical generator scripts are preserved and should not be rerun in place,
because they overwrite historical evidence. Do not add private inputs to this tree.
