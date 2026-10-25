# Documentation structure

Choose the owner before writing. Link to its document; do not copy instructions.

## Owners

| Location | Purpose | Put new content here |
| --- | --- | --- |
| `README.md`, `docs/README.md` | Navigation | Short introductions and links |
| `docs/ARCHITECTURE.md` | Desired system | Topology, ownership, policy and accepted limits |
| `runbooks/` | Installation, maintenance and live recovery | Prerequisites, ordered actions, stop conditions and final checks |
| `docs/operations/` | Recurring operations and verification | Monitoring response, interpretation and scheduled exercises |
| `docs/testreports/IMPLEMENTATION_PLAN.md` | Current phase status and remaining work | Objectives, status, implementation gaps, verification gaps and evidence links |
| `docs/testreports/phases/phase-NN/REPORT.md` | One primary phase summary | Dated result, verification, limits and history links |
| `docs/testreports/phases/phase-NN/history/` | Earlier phase execution | Original outcomes, commands and diagnostics |
| `docs/testreports/incidents/` | Incident records | Impact, timeline, diagnosis, recovery and evidence |
| `docs/testreports/decisions/` | Historical design decisions | Decision, reason, scope and supersession links |
| `docs/testreports/archive/` | Retired plans, prompts and migration procedures | One-time instructions with historical context |
| `docs/testreports/evidence/` | Sanitized execution records and artifacts | Dated metadata, results, logs and screenshots |
| `recovery/README.md` | Private recovery inputs | Input schema, preservation and off-host requirements |

Existing self-contained DR and application-source archives retain their paths
for recorded scripts, provenance and checksum compatibility. Index them from
the reports directory. Do not use archived scripts as current runbooks.

## Names and content

- Use lowercase kebab-case names: `2026-10-25-backup-check.md`.
- Use ISO dates and UTC for execution times. Name environments explicitly.
- Keep established `README.md`, `REPORT.md` and `IMPLEMENTATION_PLAN.md` entrypoints.
- Use `phase-00` through `phase-11`; keep sub-checkpoints such as 10.2 in Phase 10.
- Name artifacts by environment and purpose, for example `prod-capacity.png`.
- Use short sections and direct sentences. Put the result or required action first.
- Use checklists for actions and tables for comparisons. Keep execution details that affect interpretation.

## Status and history

- Update the plan and primary report together when evidence changes status.
- Separate implemented functionality, recorded successful checks, remaining implementation and remaining verification.
- Give every summary an explicit “as of” date. Saved evidence is not current health.
- Preserve failed and blocked outcomes. Add a dated correction or later record; do not turn an old failure into a pass.
- Keep previous reports under `history/`. Put one primary summary on the main reading path.
- Mark retired decisions “superseded” and link both directions to their replacement. Accepted design belongs in architecture.
- Mark archived prompts as records, never active instructions or fresh authorization.
- Use relative links and stable heading anchors. Repair inbound links when moving a file, including links outside `docs/`.
- Keep immutable source URLs and original executable snapshots unchanged. State their source context in the archive index.

Permanent manuals must not contain incident resource IDs, build receipts,
old execution status, agent prompts, chat transcripts, temporary approvals,
legacy-cluster migration sequences or speculative completion claims.
Credentials, private evidence, Terraform state and recovery archives must never
enter Git. Follow [recovery preservation rules](../recovery/README.md).

## Minimal records

Phase report:

```text
# Phase NN — Objective
Summary as of YYYY-MM-DD. Environment: ...
## Result
Implemented scope and status.
## Recorded verification
Check | result | evidence link
## Limits and remaining work
Separate implementation from verification.
## Records
Earlier executions, evidence and authoritative procedures.
```

Incident:

```text
# YYYY-MM-DD — Incident
Environment: ...  Impact: ...  Status as of <UTC time>: ...
## Timeline
UTC time | observation or action | result
## Diagnosis
Confirmed cause; uncertainty; unique failure diagnostics.
## Recovery and verification
Actions performed and observed results; link the reusable runbook.
## Follow-up and evidence
Open implementation/verification, sanitized records, private evidence location.
```

Evidence record:

```text
# YYYY-MM-DD — Verification purpose
Environment: ...  Source revision: ...  Method: live/local/fixture/simulation
## Result
Artifact link | check/result | what it establishes
## Limits
What was blocked or not checked; private evidence location, without values.
```

## Before each documentation change

- [ ] Read this file, applicable AGENTS.md, the owner document and relevant indexes.
- [ ] Choose one purpose and an authoritative location. Link existing procedures.
- [ ] Check dates, source revisions, evidence and open gaps before changing status.
- [ ] Preserve unique commands, failure diagnostics, evidence and operator scripts.
- [ ] Repair local links, anchors and moved-path references; check artifact hashes.
- [ ] Review for private data and unrelated or functional changes. Run `git diff --check`.
- [ ] Review the staged diff. Use a focused commit with an explanatory body.
