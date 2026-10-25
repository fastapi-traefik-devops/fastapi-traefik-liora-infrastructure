# Phase 5 report — PROD deployment and three-environment acceptance

Status on 2026-10-21: **complete**. Phase 6 has not started.

## Source and deployment scope

After the verified migration was fast-forwarded into the original checkout,
the operator authorized the next phase. Work continues on `main` in
`/home/root-admin/fastapi-traefik-liora-infrastructure`; the merged migration
branch and worktree were already removed. Initial manifests were applied from
`3cd58eb3836502229a701aa55a4b26a969f594bd`. The final backend compatibility
change is `30a465e0964ebf863b96f2e6ab7a81c079491080`.

Deployment source remains the imported application history at
`b98a22e48527c256193ed65c10307eb574b27ab6`. The read-only application checkout
is now clean at that same commit; it was not updated or modified by this phase.
No history was rewritten and nothing was pushed.

Every PROD cluster operation used the explicit
`/home/root-admin/.kube/config-prod` kubeconfig, verified API
`https://192.168.77.12:6443`, namespace `app-prod`, and nodes `k3s-2-01`–`03`
(VMs 211–213). Nonprod checks used the explicit dev/stage kubeconfig. The kind
reference cluster was not changed.

## Database-first deployment and compatibility correction

Strict offline recovery validation passed with zero errors and warnings.
PROD's backend/database Secrets matched recovery in memory; no credential
values were printed or changed. Before deployment, PROD had no application
Deployments, PVCs or Jobs. The overlay rendered 13 objects, split into the
existing 3/2/1/7 configuration-storage/database/prestart/application groups.

ConfigMaps, PVC, database Service and PostgreSQL were applied first. The claim
became Bound, PostgreSQL became Ready and `pg_isready` accepted connections.
Only then was prestart created. It completed once, from `16:21:56Z` to
`16:23:01Z`; the database reports Alembic revision `1a31ce608336`. The remaining
application group was applied after that completion.

The initial PROD backend used the image default, `fastapi run --workers 4
app/main.py`. Both replicas repeatedly logged child-process deaths and stayed
unready. Neither container restarted. Their cgroup `oom` and `oom_kill`
counters were zero, memory limit 512Mi, observed memory peaks approximately
173Mi and 165Mi. These observations do not establish a memory failure or the
underlying cause of the multiworker startup problem.

Commit `30a465e` gives PROD the explicit single-worker command already verified
in DEV/STAGE and documents it in the runbook. Image pins, resource limits and
two backend replicas were retained. The operator noted the slow server; the
rollout was allowed to finish without further configuration changes. Both new
replicas became Ready and the old replicas were removed by the Deployment.
No PVC, database or successful prestart Job was recreated. Initial startup
probe connection refusals resolved after readiness.

Final state: backend **2/2**, frontend **2/2**, PostgreSQL **1/1**, Adminer
**1/1**, prestart **Complete**; all final container restart counts are zero.
PROD's separate 1Gi RWO `postgres-vol` is Bound through `local-path` to
`pvc-88624c85-5bec-4af4-87fa-0654754f718e` on `k3s-2-02`. DEV and STAGE retain
their distinct volumes and data.

## Applied images and actual placement

The approved application tag remains
`sha-c375967ac5b3dd7a0a6867758e16b057c733bb2d`. Both backend replicas and
prestart use digest
`sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d`;
both frontend replicas use
`sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91`.
Actual Kubernetes container image IDs match these rendered pins.

| Component | Actual nodes | Actual image digest |
| --- | --- | --- |
| Backend, two replicas | k3s-2-01, k3s-2-03 | `sha256:f1a896fbc915f1f19416882fee62bf4db275860f9225d9004ac59ba9a005dc5d` |
| Frontend, two replicas | k3s-2-02, k3s-2-03 | `sha256:7d1ac191287e0498434049d4e569aa8f8a8ed2dbd19921e20bc566c95b2a4c91` |
| Prestart | k3s-2-03 | Same backend digest |
| PostgreSQL 16.6 | k3s-2-02 | `sha256:557fea37a744d5f4c8faab304b0a90858b53ab119735a88c131fd19dab802f36` |
| Adminer 4.8.1 | k3s-2-03 | `sha256:34d37131366c5aa84e1693dbed48593ed6f95fb450b576c1a7a59d3a9c9e8802` |

## Private acceptance, isolation and cleanup

The existing browser script used `http://liora.aprt.info:18080`, resolving that
hostname to loopback inside Chromium. A localhost-only PROD Traefik forward
served port 18080; the independent nonprod forward used port 18081. No public
DNS, system hosts, edge routing or certificate changes were made.

PROD passed health HTTP 200/`true`, frontend/login HTTP 200, actual UI login,
item creation, editing, persistence after page reload and authenticated API
read. Its test item was `8efa7d8d-ef32-4239-875c-b4adb6b6d12f`, titled
`acceptance-prod-656862e2c744-updated`.

All three environments authenticated independently and returned their own
marker/title with HTTP 200. Each returned HTTP 404 for both other environments'
markers and HTTP 403 for both foreign signed tokens. Read-only SQL confirmed
marker counts in DEV/STAGE/PROD order of `[1,0,0]`, `[0,1,0]`, and `[0,0,1]`.
All six directed marker checks and all six foreign-token checks passed.

After all isolation checks passed, only the three exact synthetic acceptance
items were deleted through their owning authenticated APIs. Their absence was
confirmed with API 404 and SQL counts `[0,0,0]` in every database; health was
rechecked successfully. Acceptance records now mark their items as removed.
The historical Phase 3/4 reports describe when their markers were retained;
those markers are no longer present after this phase.

Nonprod workload snapshots exactly match the Phase 4 snapshots: same Pod names,
image IDs, volume bindings, Ready replicas and zero restarts. All six nodes
were Ready at final verification. Both temporary port-forwards were stopped.

Local evidence under `/home/root-admin/liora-render/` includes
`prod/acceptance.json`, `prod/isolation.json`, `prod/marker-cleanup.json`, and
`{dev,stage,prod}/phase5-workloads.json`. The local `prod/check-isolation.py`
and `prod/record-workloads.py` save only result metadata. The isolation helper
reads recovery at runtime; no passwords, tokens, browser state or traces were
saved.

## Repository changes and remaining boundaries

- `kubernetes/apps/liora/overlays/prod/kustomization.yaml`: explicit one-worker
  command, retaining two PROD backend Pods.
- `runbooks/13-deploy-application-manifests.md`: compatibility guidance, verified
  three-environment status and original-checkout recovery location.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/testreports/archive/migration-procedures/application-source-history.md`, and
  `docs/testreports/IMPLEMENTATION_PLAN.md`: current deployed state, integration
  location, completed Phase 5 checklist and marker cleanup.
- `docs/testreports/phases/phase-05/history/execution-2026-10-21.md`: this evidence and limitation record.

Recovery files and both unrelated untracked Kubernetes documents remain
unchanged. No live credential, private key or Terraform state was committed.

All Phase 5 checks passed. This proves private functional acceptance of the
current stack; it does not establish load capacity, public routing, trusted
TLS/canonical HTTPS, backup restoration, node failover or replicated database
storage. STAGE/PROD retain their `app-tls` references without newly provisioned
TLS Secrets. The multiworker startup cause remains open; keep the verified
single-worker configuration unless separately tested.

Next after confirmation: Phase 6, separate Argo CD installations and reviewed
ownership reconciliation on each cluster. Public routing remains Phase 7.
Do not start Phase 6 as part of this increment.
