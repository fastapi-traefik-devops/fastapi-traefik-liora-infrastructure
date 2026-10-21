# Phase 8 — Operational access and monitoring

Date: 2026-10-21. Status: **in progress; partial NONPROD deployment, blocked on
ServiceLB status ownership**. The operator authorized execution of the updated
plan. This report does not mark Phase 8 complete or authorize Phase 9.

## Implemented and observed

- Rechecked clean, read-only application source at
  `b98a22e48527c256193ed65c10307eb574b27ab6`.
- Preserved selected `monitoring/` and `infra/jenkins-host/` history under
  `kubernetes/platform/upstream/`: 22 imported commits, original authors/dates/
  messages, merged without squashing/rebasing existing history. Import tip
  `859a076cd30e19b242c2653d97826d1fd05fd9af`, integration commit `53dcf18`.
  No additional working checkout was created.
- Prepared separate services-only kube-vip v1.2.3 DaemonSets with independent
  names/selectors/RBAC, global service election (`svc_election=false`), common
  per-cluster lease `kube-system/liora-admin-services`, metrics 2113, and strict
  class `liora.aprt.info/admin-vip`. Services explicitly request their Admin
  VIP and disable NodePort allocation. API kube-vip stays unchanged on 2112.
- Applied only NONPROD's new DaemonSet/RBAC and private Services. All three
  kube-vip-admin Pods are Ready. The observed leader was `k3s-1-02`; all six
  private Services carry its `kube-vip.io/vipHost` annotation. This observation
  does not prove host-level absence of a second address owner or failover.
- Initial direct-VIP Argo browser login and authenticated user-info check
  passed at `https://192.168.77.16:8080`, with native bootstrap TLS. DEV/STAGE
  Adminer Services received `.16:8081` and `.16:8082`. Stable acceptance and
  Adminer database browser logins remain pending because of the issue below.
- Installed NONPROD Helm release `monitoring`, pinned kube-prometheus-stack
  92.2.0. All eight Pods are Ready with zero restarts. Prometheus 2Gi and
  Alertmanager 256Mi PVCs are Bound on `local-path`.
- Adapted source values, four dashboards, Argo/Traefik monitors and eight rules
  for each cluster. K3s Traefik labels/namespace replace the kind assumptions;
  PROD application queries select only `app-prod`. Cluster identity is explicit
  in datasource names, dashboard titles, rule labels and Prometheus external
  labels. External labels are not assumed to appear in local time series.
- Internal Prometheus diagnostics through the Kubernetes API service proxy
  found **26/26 targets up**, all eight rules healthy, three node-exporter
  identities, three Kubernetes nodes, application Deployment metrics, three
  Argo Applications and Traefik metrics. This diagnostic path is not the
  required browser/Admin VIP acceptance and does not establish Tailscale access.
- Provisioned fresh NONPROD Grafana and Jenkins-foundation credential inputs
  outside Git. The helper preserves existing login Secrets and writes private
  recovery JSON with mode 0600. No publishing keys or jobs are mounted.
- Published the unchanged existing PoC controller image to GHCR, without a
  rebuild/core/plugin upgrade. Registry digest:
  `ghcr.io/fastapi-traefik-devops/liora-jenkins-controller@sha256:7c7e8f8806b7c6aba679aee7cfaec51c0b40475cf536958be8146885e7b310ad`.
  The running PoC image's plugin lock matches the imported source. Prepared a
  zero-executor/no-agent/no-job controller with native `.16:8085` URL, 5Gi PVC
  and bounded resources. **No Jenkins Deployment, Pods or PVC have been created**;
  only its namespace/login/pull Secret prerequisites exist.

## Blocking incompatibility: ServiceLB still writes foreign status

The installed K3s version is `v1.36.5+k3s1`. LoadBalancer class correctly avoids
creation of administrative `svclb-*` DaemonSets. However, its separate
`onChangeEndpointSlice()` worker queues every Service, and `updateStatus()`
checks only `ServiceTypeLoadBalancer`, without checking `loadBalancerClass`.
It then calculates status from nonexistent administrative ServiceLB Pods and
clears the kube-vip address.

Observed on NONPROD monitoring Services: kube-vip initially wrote `.16`, then
`service-lb-controller` emitted `UnAvailableLoadBalancer` and status became
empty/Pending as backend endpoints changed. VIP HTTP connections then failed
despite Ready Pods. Argo/Adminer are subject to the same future endpoint-change
risk; their initially successful access is not stable acceptance.

Pinned source:
[K3s ServiceLB worker](https://github.com/k3s-io/k3s/blob/v1.36.5%2Bk3s1/pkg/cloudprovider/servicelb.go),
[kube-vip global ARP service election](https://github.com/kube-vip/kube-vip/blob/v1.2.3/pkg/manager/worker/arp.go),
[kube-vip class filter](https://github.com/kube-vip/kube-vip/blob/v1.2.3/pkg/services/watch_services.go).
The inspected K3s master source also lacks the class guard; a verified fixed
release has not been identified. Do not silently upgrade/restart K3s or disable
ServiceLB, which would change the reviewed public-ingress boundary.

A [concrete ownership guard proposal](../../kubernetes/platform/proposals/README.md)
and [native admission manifest](../../kubernetes/platform/proposals/admin-status-ownership.yaml)
are prepared but **not applied**. Server dry-run passed. The guard restricts
status writes only for the administrative class to its kube-vip service account.
It uses no extra Pods and leaves API/Traefik/network policies unchanged, but
ServiceLB may retry rejected writes and emit denial logs. Enforcement and retry
behavior require NONPROD verification after the operator chooses this mechanism.
The operator was asked whether to use this guard or separately revisit K3s/
ServiceLB integration. PROD rollout is paused until this real incompatibility
is resolved; no architecture workaround has been silently deployed.

## Checks and preservation

- All six nodes were Ready; all five existing Argo Applications remain
  Synced/Healthy after NONPROD changes.
- Every original Deployment/PVC/Service UID **and spec** matches its pre-change
  snapshot in both clusters. Both original API kube-vip DaemonSets and public
  Traefik/ServiceLB were left unchanged.
- Three environment overlays render. Admin access server dry-runs pass in both
  clusters; Jenkins foundation dry-run passes in NONPROD. PROD was dry-run only.
- Python syntax and three fixture tests pass, including existing-Secret
  preservation and success/failure diagnostic checks that do not print fixture
  secret values. Active NONPROD and PROD manifest scans find no secrets.
- Source-history scanning reviewed 19 nonempty selected commits. All 27
  generic-key findings were public plugin-version entries; each flagged artifact
  resolved on updates.jenkins.io. Rescan passed with only that file/rule excluded;
  other files/rules stayed enabled. See upstream provenance README.
- Native Grafana/Jenkins and Adminer login acceptance, dashboard browser checks,
  direct monitoring VIP metrics checks and external Tailscale browser access are
  pending. The reusable browser helper is prepared but its full path is not
  claimed verified while VIP routing is broken.
- No new public routes/NAT, DNS records, Tailscale ACL/grants or firewall changes.
  Public-origin reachability acceptance has not yet been run. VM 100 and its
  Jenkins/kind data, legacy NAT, VM 200 state/certificate automation and existing
  recovery files are preserved. No Git push was performed.
- Attempts to read additional node address lists stopped at SSH host-key trust
  checks; the Proxmox guest-agent alternative was unavailable. Neither check
  changed trust settings or constitutes a failover test.

## Files, evidence and remaining order

Active configuration is under `kubernetes/platform/{base,nonprod,prod}/`;
private Adminer Services sit in each existing application overlay. The concrete
procedure and recovery boundaries are in
[runbook 16](../../runbooks/16-private-platform-access.md), with direct links to
standalone credential/browser scripts. Reference-only upstream source and the
pending policy proposal are explicitly separated from installation entrypoints.

Ignored evidence is in `.local-work/phase8/`, including pre-change inventories,
original-resource comparisons, Helm state/log, internal targets/rules/query
counts, status-conflict Service/events, chart/source snapshots and scan review.
Private inputs are in `.local-work/private/platform/`; registry client auth is
in `.local-work/phase8/docker-auth/`. Preserve these as protected operator data,
not Git content. The chart archive is under `.local-work/charts/` and its hash
is tracked in `kubernetes/platform/chart-lock.json`.

Next, after resolving the ownership decision: verify NONPROD stable status and
native browser access; complete NONPROD dashboard/metrics acceptance; deploy and
verify independent PROD; deploy the prepared NONPROD Jenkins foundation; record
public-route boundaries and external Tailscale acceptance. Keep all Phase 8
checkboxes uncompleted until their full stated checks pass. Working CI and
promotion migration remain Phase 9; no failover/reboot/load tests are required.
