# Kubernetes implementation plan

Status reconciled from repository records as of **2026-10-25**.
This is a work register. Reports provide dated evidence; they do not prove
current health. Desired design: [architecture](../ARCHITECTURE.md).
Actions: [runbooks](../../runbooks/README.md).

## Phase status

| Phase | Objective | Recorded status | Primary report |
| --- | --- | --- | --- |
| 0 | Establish baseline | Review and later storage checks recorded | [00](phases/phase-00/REPORT.md) |
| 1 | Import application deployment history | Local import/render complete | [01](phases/phase-01/REPORT.md) |
| 2 | Prepare namespaces and credentials | Complete | [02](phases/phase-02/REPORT.md) |
| 3 | Deploy DEV | Private acceptance passed | [03](phases/phase-03/REPORT.md) |
| 4 | Deploy STAGE | Acceptance and isolation passed | [04](phases/phase-04/REPORT.md) |
| 5 | Deploy PROD | Private acceptance passed | [05](phases/phase-05/REPORT.md) |
| 6 | Separate GitOps ownership | Adoption and drift checks passed | [06](phases/phase-06/REPORT.md) |
| 7 | Publish applications | DNS-only origin acceptance passed | [07](phases/phase-07/REPORT.md) |
| 8 | Monitoring and private access | Functional checks complete; failover untested | [08](phases/phase-08/REPORT.md) |
| 9 | Move CI/CD ownership | Delivery/release/rollback recorded; follow-up open | [09](phases/phase-09/REPORT.md) |
| 10 | Replace databases and implement backups | 10.1/10.2 passed; full DR unverified | [10](phases/phase-10/REPORT.md) |
| 11 | Certificates and DHCP refinement | Defined scope complete; scheduled renewal observation open | [11](phases/phase-11/REPORT.md) |

## Phase 9 — Move promotion and CI ownership

Implemented and recorded: PR/nightly full gates, manual DEV, automatic STAGE
acceptance, reviewed PROD releases, live rollback and reproducible observer
bundle checks. [Evidence](phases/phase-09/history/target-state.md).

| Type | Remaining task |
| --- | --- |
| Implementation | Make application health and STAGE acceptance check database connectivity. |
| Implementation | Automate trusted bundle-pin PR preparation. |
| Verification | Exercise failed acceptance, stale candidates and concurrent updates live; fixtures alone do not close these cases. |
| Verification | Verify held-controller restart and policy restoration. |
| Verification | Check the `unchanged` re-release result live. |
| Status check | Establish whether application cleanup PR #78 merged; retain the [cleanup record](evidence/records/application-repository-cleanup.md). |

Older scan deferrals, “PROD blocked” and main-only schedule statements remain
in [Phase 9 history](phases/phase-09/REPORT.md#records). They are superseded
for the delivery scope established by the target-state report.

## Recovery and operational follow-up

| Type | Remaining task | Basis / procedure |
| --- | --- | --- |
| Verification | Exercise live CNPG restore and cutover, stable endpoint, ownership and post-recovery archiving. | [Implementation record](evidence/records/2026-10-25-recovery-runbooks.md); [runbook 20](../../runbooks/20-restore-live-postgresql.md) |
| Verification | Exercise three-server etcd restoration and original-token decryption. | [Runbook 21](../../runbooks/21-restore-k3s-etcd-snapshot.md) |
| Verification | Restore a stopped current-K3s Jenkins home into an isolated held controller; check login, credential decryption, history and agents. | [Procedure implementation](evidence/records/2026-10-25-jenkins-recovery-runbooks.md); [runbook 23](../../runbooks/23-restore-jenkins-controller.md) |
| Verification | Verify replacement coordinator access, Grafana login, jobs/observer, HTTPS and application login/CRUD on rebuilt clusters. | [Documentation closure](evidence/records/2026-10-25-operational-documentation-closure.md) |
| Operator action | Create the updated encrypted recovery kit, keep it off-host and verify retrieval with matching state/private inputs. | [Etcd record](evidence/records/2026-10-25-etcd-r2-backups.md); [recovery inputs](../../recovery/README.md) |
| Verification | Perform independent full-system DR, including private kit/state retrieval. | [Saved DR limits](disaster-recovery-test/README.md) |
| Decision / implementation | Define protection and restoration for Prometheus/Alertmanager history and other persistent volumes. PostgreSQL backups do not cover them. | [Recovery capability review](evidence/records/2026-10-24-operational-documentation-review.md#recovery-capability-register) |
| Recurring verification | Repeat sequential isolated PITR monthly and after mechanism changes; measure elapsed retention coverage. | [Verification procedure](../operations/POSTGRESQL_BACKUP_VERIFICATION.md) |
| Verification | Observe first scheduled unattended application-certificate renewal. | [Phase 11](phases/phase-11/REPORT.md) |
| Verification | Reconcile private tfvars with fixed 8192 MiB/no-ballooning provisioning; verify guest and kubelet capacity during planned maintenance. | [Memory implementation record](evidence/records/2026-10-25-k3s-fixed-memory.md) |

Observer pin alignment and a bounded connection installer were open in the
closure record. The later [target-state report](phases/phase-09/history/target-state.md#8-reproducible-observer-installation)
records their implementation and local checks. This closes those implementation
items, not the rebuilt-controller runtime exercise.

## Separate reviews

- Review SQLAlchemy reconnect behavior against the application change and its tests; the saved plan does not establish merge or deployment.
- Reconcile recovery validator fields and fake examples with the private-input model while preserving older archives.
- Review resource budgets, logging, alert delivery, HPA/PDB and PROD application placement before implementation. These are open proposals, not completed capabilities.
- VIP failover, node-failure behavior and monitoring-history recovery remain unverified.

Optional longer-term edge redundancy and PROD Adminer reviews belong to
[architecture](../ARCHITECTURE.md#optional-longer-term-improvements).
Earlier objectives, commands, approvals, incident diagnoses and receipt tables
are preserved in each phase's `history/plan-notes-2026-10-25.md`,
[platform planning](archive/plans/platform-plan-2026-10-25.md) and
[recovery planning](evidence/records/2026-10-25-recovery-planning-notes.md).
