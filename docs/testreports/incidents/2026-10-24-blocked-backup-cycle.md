# Backup incident — 2026-10-24: blocked cycle after STAGE delay

Status: **recovered at 12:56 UTC on 2026-10-24**. The retained cycle completed,
its global fence was released, the old systemd failure flag was cleared, and
the existing daily timer was restored. Its next invocation is 2026-10-25 at
02:00 UTC; that future invocation has not yet been observed.

This report records the incident, investigation and manual recovery. The
permanent backup design and operator procedures remain in
[runbook 19](../../../runbooks/19-cnpg-r2-backup-pitr.md). The existing
[coordinator](../../../scripts/backups/coordinator.py) performed recovery without
code, credentials, retention, database or application changes.

## What happened

All timestamps below are UTC. Cycle ID: `221a6dbdfd804a04813c760e71b1d2f8`.

| Time | Event |
| --- | --- |
| Oct 23 18:11 and 18:36 | Kubelet rejected STAGE PostgreSQL Pod admission with `OutOfmemory` |
| Oct 24 02:00:00 | VM 250's scheduled `liora-backup.service` started |
| 02:00:42 | Coordinator recognized PROD backup completion and created STAGE Backup |
| 04:00:46 | STAGE was still nonterminal/unknown to the coordinator after its two-hour observation deadline |
| 04:00:46 | Coordinator exited with status 1, retained the global fence and left DEV unstarted |
| 07:01:20–07:02:15 | STAGE's recorded reconciliation began and completed successfully |
| 12:55:36 | Explicit resume recognized STAGE completion; only missing DEV Backup was created |
| 12:55:52 | DEV physical backup finished |
| 12:56:26 | Coordinator observed DEV completion, finished the original cycle and released the fence |

The service error was:

```text
Coordinator stopped: Backup remains running or unknown at observation deadline
```

This was an observation timeout, not a systemd eight-hour timeout or a confirmed
failed R2 upload. STAGE eventually completed successfully, but the already
exited coordinator could not observe that or advance to DEV automatically.
Keeping the fence and stopping advancement was the intended safety behavior.

## Memory findings and limits of the diagnosis

The owner reported fixing a discrepancy between VM RAM and Kubernetes' recorded
node capacity. Historical metrics confirm that Kubernetes advertised only about
2.05, 1.76 and 2.45 GiB on the three NONPROD nodes overnight. By the 07:30 sample,
all three advertised approximately 7.76 GiB again, consistent with 8 GB guests.

The `k3s-1-02` journal contains direct evidence:

```text
Pod admission denied
pod="app-stage/liora-db-1"
reason="OutOfmemory"
Node didn't have enough resource: memory,
requested: 671088640, used: 1879048192, capacity: 2237489152
```

That is a 640 MiB request against approximately 1792 MiB already accounted for
and only 2134 MiB of recorded capacity. This establishes a real memory-accounting
problem that prevented STAGE PostgreSQL admission. The underlying VM/K3s fix was
performed by the owner, not by this recovery operation.

The initial investigation incorrectly ruled out memory based on container
working sets, lack of OOM-kill counters and guest-OS available memory. That
conclusion is withdrawn: admission rejection can happen without a kernel OOM
kill, and guest memory availability does not prove Kubernetes has the correct
allocatable capacity. Historical node capacity/allocatable must be checked too.

Controller/API instability and later restarts were also observed. Older CNPG
controller container logs had rotated away, so the complete causal chain behind
the five-hour reconciliation delay is not proven. Memory accounting is a
confirmed contributing infrastructure fault and a strong explanation, not proof
of every intermediate failure. No evidence established a credential or R2
upload failure as the trigger.

## Checks before recovery

- VM 250's coordinator service was failed and not running; its daily timer was
  enabled. The restricted `inspect` action showed the original held cycle:
  PROD completed, STAGE creating, DEV planned, with `blocked_at` recorded.
- The actual PROD and STAGE Backup resources were already completed. No
  nonterminal Backup existed in any of the three application namespaces.
- All six cluster nodes were Ready and again advertised more than 7 GiB
  allocatable RAM. All live database Clusters were Ready.
- Backup resource identities matched the names retained in the cycle journal.
  Nothing was deleted or recreated to hide the incident.

## Manual operator recovery

Use this procedure for the same situation: the coordinator has stopped, its
recorded backup has subsequently reached a terminal state, and infrastructure
health has been restored. Do not use it to take over a healthy active owner.

### 1. Inspect cluster health from a trusted administrator workstation

Use the original checkout and explicit administrator kubeconfigs:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" --request-timeout=30s get nodes -o 'custom-columns=NAME:.metadata.name,CAPACITY:.status.capacity.memory,ALLOCATABLE:.status.allocatable.memory'
kubectl --kubeconfig="$HOME/.kube/config-prod" --request-timeout=30s get nodes -o 'custom-columns=NAME:.metadata.name,CAPACITY:.status.capacity.memory,ALLOCATABLE:.status.allocatable.memory'
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" --request-timeout=30s -n cnpg-system get deployments,pods
kubectl --kubeconfig="$HOME/.kube/config-prod" --request-timeout=30s -n cnpg-system get deployments,pods
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" --request-timeout=30s -n app-dev get clusters.postgresql.cnpg.io,backups.postgresql.cnpg.io
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" --request-timeout=30s -n app-stage get clusters.postgresql.cnpg.io,backups.postgresql.cnpg.io
kubectl --kubeconfig="$HOME/.kube/config-prod" --request-timeout=30s -n app-prod get clusters.postgresql.cnpg.io,backups.postgresql.cnpg.io
```

Require healthy nodes/controllers/databases and plausible capacity/allocatable
values for the configured VMs. Compare backup names and phases with `inspect`
below. For this incident, PROD/STAGE had to be completed and DEV absent. If a
Backup is still running, wait for completion before following this completed-
backup recovery path. If an API is unavailable or another operation is active,
stop and investigate; do not infer a safe state from elapsed time alone.

For memory diagnosis, inspect the affected node's K3s journal for the incident
window, for example directly on that node:

```sh
sudo journalctl -u k3s --since '2026-10-23 17:00:00 UTC' --until '2026-10-24 07:05:00 UTC' --grep='OutOfmemory|Insufficient memory|Pod admission denied' --no-pager
```

Compare historical `kube_node_status_capacity{resource="memory"}` and
`kube_node_status_allocatable{resource="memory"}` against
`node_memory_MemTotal_bytes`. Current `kubectl top` and absence of `OOMKilled`
alone cannot exclude yesterday's admission failures.

### 2. Inspect and pause scheduling on VM 250

Connect through the established trusted SSH path. For this checkout, VM 250's
verified host key is in `.local-work/private/phase10-2/known_hosts`:

```sh
ssh -i recovery/LIORA-id_ed25519 -o UserKnownHostsFile=.local-work/private/phase10-2/known_hosts -o StrictHostKeyChecking=yes root-admin@192.168.77.250
```

Run the following commands **on VM 250**. Record the timer's original enabled
and active state before changing it:

```sh
systemctl is-enabled liora-backup.timer
systemctl is-active liora-backup.timer
systemctl show liora-backup.service -p ActiveState -p SubState -p Result -p ExecMainStartTimestamp -p ExecMainExitTimestamp
sudo journalctl -u liora-backup.service --since '24 hours ago' --no-pager
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
sudo systemctl stop liora-backup.timer
```

For this incident the timer was enabled/active and the service failed/inactive.
Do not stop a running backup service or start a second owner. `inspect` uses
the same local lock; an active-owner/lock refusal is a reason to stop, not to
remove the lock file. Stopping the timer prevents a scheduled start during
manual recovery; it does not disable it or stop an already running service.

### 3. Resume the retained cycle, not a fresh cycle

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py resume
```

[Standalone coordinator source](../../../scripts/backups/coordinator.py).

Keep the session connected until it exits. In this incident resume:

1. Retained the original cycle ID and selected a new owner-session fence.
2. Skipped PROD, already terminal in its journal.
3. Observed the existing STAGE Backup and recorded its completed status.
4. Created exactly one DEV Backup using the original deterministic name.
5. Observed DEV completion, released the global fence and sent the coordinator's
   blocked-condition resolution notification to Alertmanager.

Do not run `run` instead of `resume`, manually delete/edit the Lease, remove
`cycle.lock`, delete Backup resources, or patch phases to completed. None is
needed here. A definitively failed full backup is recorded and not retried by
resume; a zero exit code therefore does not by itself prove every backup passed.

If resume fails or the SSH session is interrupted, leave the timer stopped,
preserve evidence and inspect service/process, Lease and named Backup state
again before attempting another explicit resume. Do not immediately launch a
second process or assume an interrupted SSH connection stopped the first one.

### 4. Verify completion before clearing the old service failure

On VM 250:

```sh
sudo -u liora-backups /opt/liora-backups/venv/bin/python /opt/liora-backups/coordinator.py inspect
```

Require an empty `holder`, a `finished_at` timestamp and the expected terminal
status of each step. For successful recovery of this incident all three steps
must say `completed`. From the trusted workstation, repeat the three namespace
Backup checks in step 1 and inspect any discrepancies before proceeding.

Only after those checks pass, on VM 250:

```sh
sudo systemctl reset-failed liora-backup.service
sudo systemctl start liora-backup.timer
systemctl show liora-backup.service -p ActiveState -p SubState -p Result
systemctl is-enabled liora-backup.timer
systemctl is-active liora-backup.timer
systemctl list-timers liora-backup.timer --no-pager
systemctl is-active liora-backup-metrics.service
```

This restores the previously enabled/active timer. If it had been intentionally
disabled/inactive before the incident, preserve that original state instead.
Do not start another full cycle merely to clear systemd's failure flag.

`liora-backup.service` is oneshot: `inactive/dead` while idle is normal.
`reset-failed` clears the old failed state; it does not execute a backup. Since
resume runs the CLI directly, the service's old timestamps/journal still refer
to the scheduled attempt. The new completed cycle journal is the recovery
evidence. Successful resume does not prove tomorrow's timer invocation.

## Actual recovery result

All resources below belong to the original retained cycle; PROD/STAGE were not
rerun and their original physical IDs were preserved.

| Environment | Backup resource | Physical backup ID | Physical completion UTC |
| --- | --- | --- | --- |
| PROD | `bk-221a6dbdfd804a04813c760e-prod` | `20261024T020007` | 02:00:16 |
| STAGE | `bk-221a6dbdfd804a04813c760e-stage` | `20261024T070125` | 07:01:41 |
| DEV | `bk-221a6dbdfd804a04813c760e-dev` | `20261024T125540` | 12:55:52 |

Final verification at 12:56–12:57 UTC:

- Lease holder empty; all three cycle steps completed; `finished_at` recorded.
- Coordinator telemetry: `held=0`, `blocked=0`, `ok=1`; each environment has
  `nonterminal=0`, `ok=1` and a recorded successful backup.
- Service `Result=success`, `ActiveState=inactive`, `SubState=dead` after clearing
  the stale failure. Timer enabled/active, next run 2026-10-25 02:00 UTC.
- Metrics service active and all database Clusters report continuous archiving
  healthy. No database reset, PVC deletion, application rollout or Jenkins change.
- No lock deletion, new backup cycle, failed-backup retry, retention change or
  coordinator code change was required. No new PITR exercise was performed;
  this recovery does not replace the previously agreed monthly PITR procedure.

Private evidence is retained in
`.local-work/private/incidents/2026-10-24-backup/`: the original service journal,
held-cycle Lease snapshot, pre-recovery Backup snapshots and
`recovery-result.json`. The completed cycle journal is also retained on VM 250
at `/var/lib/liora-backups/cycle-221a6dbdfd804a04813c760e71b1d2f8.json`.
These files contain operator evidence and remain outside Git.

Unrelated in-progress documentation changes in the checkout were preserved;
this incident report is a separate file and does not finalize those changes.
