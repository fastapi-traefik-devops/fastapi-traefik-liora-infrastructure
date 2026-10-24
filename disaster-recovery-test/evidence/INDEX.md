# Disaster recovery evidence index

**No real infrastructure recovery was executed.** Real evidence below is local software verification or read-only observation. Mock illustrations carry SIMULATED — NOT A REAL TEST.

[Complete report](../../DISASTER_RECOVERY_TEST_REPORT.md)

## Actual local checks and read-only observations

- [real/actual-local-checks.html](real/actual-local-checks.html)
- [real/actual-local-checks.png](real/actual-local-checks.png)
- [real/attempt-history.json](real/attempt-history.json)
- [real/jenkins-fixture-tests.log](real/jenkins-fixture-tests.log)
- [real/live-after.json](real/live-after.json)
- [real/live-before.json](real/live-before.json)
- [real/live-comparison.json](real/live-comparison.json)
- [real/local-checks.json](real/local-checks.json)
- [real/local-guard-tests.log](real/local-guard-tests.log)
- [real/local-https-results.json](real/local-https-results.json)
- [real/local-preflight.json](real/local-preflight.json)
- [real/repository-provenance.json](real/repository-provenance.json)
- [real/screenshot-render-results.json](real/screenshot-render-results.json)

## Simulated evidence and labeled example screenshots

- [simulated/01-proxmox.html](simulated/01-proxmox.html)
- [simulated/01-proxmox.png](simulated/01-proxmox.png)
- [simulated/02-kubernetes.html](simulated/02-kubernetes.html)
- [simulated/02-kubernetes.png](simulated/02-kubernetes.png)
- [simulated/03-database.html](simulated/03-database.html)
- [simulated/03-database.png](simulated/03-database.png)
- [simulated/04-application.html](simulated/04-application.html)
- [simulated/04-application.png](simulated/04-application.png)
- [simulated/05-argocd.html](simulated/05-argocd.html)
- [simulated/05-argocd.png](simulated/05-argocd.png)
- [simulated/06-jenkins.html](simulated/06-jenkins.html)
- [simulated/06-jenkins.png](simulated/06-jenkins.png)
- [simulated/07-grafana.html](simulated/07-grafana.html)
- [simulated/07-grafana.png](simulated/07-grafana.png)
- [simulated/08-completion.html](simulated/08-completion.html)
- [simulated/08-completion.png](simulated/08-completion.png)
- [simulated/09-rollback.html](simulated/09-rollback.html)
- [simulated/09-rollback.png](simulated/09-rollback.png)
- [simulated/10-cleanup.html](simulated/10-cleanup.html)
- [simulated/10-cleanup.png](simulated/10-cleanup.png)
- [simulated/results.json](simulated/results.json)

## Reproducibility and safety

The Python sources under `disaster-recovery-test/` are retained. Existing repositories were not edited. No dependencies were installed.
The mock runner uses only disposable fixtures and explicitly rejects live endpoints. The HTTPS fixture uses a disposable loopback listener.
The capture script performs read-only live metadata queries and requires the existing trusted SSH access. It is not necessary to rerun it to read these results.
SHA256SUMS paths are relative to the workspace root. The manifest excludes itself.


## Subsequent real local runtime exercise

See the [independent evidence index](../astra-review/INDEX.md) for the separate
24 October local runtime run, its limitations and 24 unique genuine screenshots.
The historical entries above are preserved.
