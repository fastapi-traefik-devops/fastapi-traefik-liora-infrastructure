# Phase 8 — Operational access and monitoring

Updated: 2026-10-22. Deployment: 2026-10-21, followed by read-only readiness and
browser checks on 2026-10-22. Status: **complete**, including operator confirmation of external Tailscale
browser access and working passwords on 2026-10-22.
Phase 9 has not started. The operator approved the status-ownership guard for
NONPROD first, then PROD; that sequence was followed.

## Deployed endpoints and verification

| Interface | NONPROD | PROD | Local functional result |
| --- | --- | --- | --- |
| Argo CD | `https://192.168.77.16:8080` | `https://192.168.77.17:8080` | Native browser login/authenticated API passed |
| Grafana | `http://192.168.77.16:3000` | `http://192.168.77.17:3000` | Login, datasource health and all four dashboards passed |
| Prometheus | `http://192.168.77.16:9090` | `http://192.168.77.17:9090` | Browser UI, 26/26 targets up and eight healthy rules per cluster |
| Alertmanager | `http://192.168.77.16:9093` | `http://192.168.77.17:9093` | Native browser UI and status API passed |
| Adminer DEV | `http://192.168.77.16:8081` | — | Database browser login passed |
| Adminer STAGE | `http://192.168.77.16:8082` | — | Database browser login passed |
| Adminer PROD | — | `http://192.168.77.17:8081` | Database browser login passed |
| Jenkins foundation | `http://192.168.77.16:8085` | — | Persistent controller/login; zero jobs, agents and executors |

These browser checks ran from the execution host on the private network, without
SSH tunnels or port-forward. They do not prove the independent external
Tailscale browser path. The operator was asked to check all deployed URLs;
on 2026-10-22 the operator confirmed all interfaces work and all passwords succeed.
This operator result completes the independent Tailscale acceptance. Argo uses
its native self-signed certificate;
trusted browser TLS for Admin VIPs was not added or promised.

Both clusters have three Ready nodes. All five existing Argo Applications remain
Synced/Healthy. Original application workloads are Ready with zero restarts.
The follow-up found both replacement Grafana instances and the Jenkins controller
Ready without restarts after approximately eight hours. This is a readiness
observation, not a failover, recovery, load or continuous-uptime test.

## Source reuse and ownership

Application source stayed clean and read-only at
`b98a22e48527c256193ed65c10307eb574b27ab6`.
Selected `monitoring/` and `infra/jenkins-host/` history was preserved under
`kubernetes/platform/upstream/`: 22 imported commits with original authors,
dates and messages. Import tip `859a076cd30e19b242c2653d97826d1fd05fd9af` was
merged at `53dcf18`, without squashing/rebasing existing history or creating
another working checkout. Upstream files are references, not active installation
entrypoints.

Helm owns the per-cluster `monitoring` release; operator manifests own the extra
scrape monitors, rules, dashboards and private Services. Existing application
Services were preserved. Each environment overlay declares a separately named
`adminer-private` Service, currently applied by the operator without Argo tracking.
Publication of reviewed source can let the existing Argo Application adopt it;
there is no competing platform Argo owner. No Git push was performed.

## Admin VIP ownership and the resolved incompatibility

Each cluster runs services-only kube-vip **v1.2.3**, with dedicated DaemonSet,
selectors, service account and RBAC. `svc_election=false` selects one global
service leader; `svc_leasename=kube-system/liora-admin-services` is independent
of the API lease `plndr-cp-lock`. Metrics use 2113 instead of API kube-vip's
2112. Services explicitly request their VIP, class `liora.aprt.info/admin-vip`,
Cluster traffic policy, and no LoadBalancer NodePorts.

| Cluster | Admin VIP | Observed common leader / physical owner | Private Services |
| --- | --- | --- | ---: |
| NONPROD | `.16` | `k3s-1-02` / VM 202 | 7 |
| PROD | `.17` | `k3s-2-01` / VM 211 | 5 |

Interface reads on all three nodes in each cluster found exactly one actual
owner, matching its lease and every Service's `kube-vip.io/vipHost` annotation.
Host keys were obtained from pre-existing trusted records on management VM 200;
SSH verification was not disabled. No administrative `svclb-*` DaemonSets or
NodePorts exist. API kube-vip and public Traefik/ServiceLB stayed unchanged.

Initial NONPROD deployment exposed a K3s `v1.36.5+k3s1` incompatibility: class
handling prevented ServiceLB DaemonSets, but its separate EndpointSlice status
worker still cleared foreign VIP status. Monitoring became inaccessible despite
Ready backends. Source inspection and `service-lb-controller` events confirmed
the cause. Class-only filtering was therefore insufficient.

The operator approved a native ValidatingAdmissionPolicy scoped to this class's
`services/status`: only `system:serviceaccount:kube-system:kube-vip-admin` may
write it. Both clusters now enforce it. Foreign status patches were rejected and
owner patches accepted using server dry-run. Ordinary EndpointSlice metadata
updates queued the conflicting worker without changing backend endpoints; VIP
status and routing remained intact. NONPROD's three already-broken private
monitoring Services were recreated once so kube-vip could reconcile them again;
no original Service or data resource was deleted.

This guard does not fix K3s: ServiceLB still retries rejected status updates and
may log denials. It does not change other Service classes, workload admission,
Tailscale access or firewall policy. No K3s binary/node restart or public-ingress
ownership change was used. See the
[approved decision](PHASE8_ADMIN_VIP_DECISION.md) and active
[status guard](../../kubernetes/platform/base/admin-access/status-ownership.yaml).

## Monitoring adaptation and operational findings

Both independent Helm releases use kube-prometheus-stack **92.2.0**; the archive
SHA-256 is tracked in `kubernetes/platform/chart-lock.json`. Adaptations replace
kind `standard` storage with `local-path`, correct Traefik namespace/labels,
preserve the datasource UID, and set cluster-specific datasource names,
dashboard titles, application selectors, URLs and rule labels. PROD queries
select only `app-prod`. Prometheus external labels are not assumed present in
local query time series.

Per cluster: Prometheus retains three days/1500MB on a 2Gi PVC; Alertmanager has
a 256Mi PVC. All four monitoring PVCs are Bound. Grafana uses provisioned,
ephemeral UI state. Exporter/operator endpoints remain internal; no additional
browser endpoints or ingress were added. External notifications are disabled
with `pending-destination`; no Slack/Telegram/email notification was sent.

The inherited Grafana 384Mi limit caused a verified OOM kill during browser
acceptance. Both clusters now request 100m/256Mi and limit 500m/768Mi, with up to
15 minutes allowed for cold startup. Replacement Pods have no recorded restarts.
PROD kube-state-metrics had one initial exit-code-2 restart, with no further
restart at the approximately eight-hour follow-up; its initial cause remains
unconfirmed. It is Ready and its metrics/target checks pass. Preserve that finding
for follow-up if it recurs; do not describe the whole rollout as restart-free.

## Jenkins foundation and private inputs

The unchanged PoC image was published without a core/plugin rebuild or upgrade:
`ghcr.io/fastapi-traefik-devops/liora-jenkins-controller@sha256:7c7e8f8806b7c6aba679aee7cfaec51c0b40475cf536958be8146885e7b310ad`.
Its mounted plugin lock matches source SHA-256
`bdd7ac49ab8d0d82aecefb51e80005c08d3d9a3c8d705d44de10d93c73cca214`.

One NONPROD controller uses a Bound 5Gi local-path home PVC, requests 100m/512Mi,
limits 1 CPU/768Mi and caps heap at 384Mi. The image pulled successfully from
GHCR; native JCasC login passed. Authenticated APIs confirmed zero jobs, zero
agents and zero controller executors. JCasC disables the inbound-agent listener;
no job-generating DSL, polling, schedules, GitHub App keys or publisher credentials
were loaded. Home contains the controller's generated config owned by UID/GID
1000. This is persistent new foundation state, not migration/backup of old home.

New random Grafana inputs are separate per cluster; the Jenkins foundation has
its own login. Files are ignored, mode 0600, under
`.local-work/private/platform/{nonprod-monitoring,prod-monitoring,nonprod-jenkins}.json`.
`bootstrap-platform-secrets.py` preserves existing login Secrets and can repair
a missing registry pull Secret independently. If both Jenkins Secrets exist,
registry inputs are not required. A live idempotence check preserved both
Secrets' UIDs/resource versions and the private input byte-for-byte. Include private
inputs in the protected operator recovery archive; never commit values. Old
recovery inputs, Jenkins home/history/encryption keys, build agents and Docker
services are preserved. Working CI/state/cutover remains Phase 9.

## Preservation, publication boundaries and checks

Every original Deployment/PVC/Service and DaemonSet UID **and spec** matched the
pre-change inventories in both clusters. All original application database
bindings, credentials, image pins and API/public ingress resources were preserved.
Three public hostnames returned frontend/backend health HTTP 200 with normal
certificate verification through edge `.240` using their real HTTPS hostnames.

Active Proxmox NAT inspection found no Admin VIP targets. Target-cluster Ingress
backends select only application frontend/backend Services. No new NAT, DNS,
HAProxy, Tailscale ACL/grants or firewall changes were made. Unauthenticated
public-origin port probes from the execution host failed; that vantage point
does not establish that every legacy public port is closed. Existing VM100
administrative NAT remains explicitly outside scope; its retirement belongs to
the operator after working CI migration. No new private interface was published.

Python syntax, five fixture cases (including success/error output redaction,
existing-login preservation and partial registry recovery), three application renders, server dry-runs and
secret scans passed. Initial selected-history scan findings were only the 27
public Jenkins plugin versions reviewed against their public artifact URLs;
a narrow file/rule exclusion was used for the reviewed history rescan. No live
credentials, private keys, state or generated private evidence became tracked.

Runbook: [16 — Private platform access](../../runbooks/16-private-platform-access.md).
Standalone scripts: [credential bootstrap](../../scripts/kubernetes/bootstrap-platform-secrets.py),
[VIP ownership verification](../../scripts/kubernetes/verify-admin-vip.py),
[native browser verification](../../scripts/kubernetes/verify-platform-access.py).
All complex operator procedures link to reusable script files.

Ignored `.local-work/phase8/evidence/` contains original-resource comparisons,
admission/VIP ownership results, browser/API outcomes, Helm records, source/scan
review, public-routing inspection and HTTPS health results. Credentials and
registry auth are protected operator data outside Git. Work remains in the
original infrastructure checkout; no temporary working clone/worktree was used.

## Final acceptance and next phase

On 2026-10-22 the operator confirmed that every interface works through Tailscale
and all passwords succeed. **Phase 8 is complete; no acceptance items remain.**
The operator also added `recovery/show_passwords.py` in commit `322b82a`;
runbooks link to this read-only, explicitly confirmed browser credential helper.
It reports stored credentials, with documented bootstrap/rotation limitations.
No live credential values were added to documentation or this report.

Phase 9 has not started. Its next work is to inventory and consistently back up
legacy Jenkins state, preserve jobs/users/history/credential IDs, adapt the
existing CI agents, isolated build daemon and trusted publisher to K3s, and
perform a controlled cutover. Promotion details remain under discussion; adapt
the existing behavior deliberately rather than inventing a new workflow.

Failover, reboot, host/storage recovery, stress/load tests and external
notification delivery were not performed and are not gates for this increment.
VM100/legacy NAT cleanup stays outside this phase and remains operator work
after working CI migration. No push was performed during phase finalization.
