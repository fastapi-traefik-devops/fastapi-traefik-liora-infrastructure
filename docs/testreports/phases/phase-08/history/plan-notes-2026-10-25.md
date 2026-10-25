# Historical phase planning and execution notes

Archived 2026-10-25 from the implementation plan. Earlier status and
authorizations describe their original checkpoint. Use the [phase summary](../REPORT.md).

## Phase 8 — Add monitoring and operational access

Status: **complete on 2026-10-22**. NONPROD then PROD were verified with the
operator-approved [status guard](../../../decisions/admin-vip-status-ownership.md). Both monitoring
stacks and the NONPROD Jenkins foundation work. The operator confirmed all
interfaces and passwords through Tailscale. See the [Phase 8 report](../REPORT.md).
Working CI migration remains a separate Phase 9 and has not started.

### 8.1 — Prepare manifests and ownership

- [x] Record the actual source revisions and current cluster resources.
      Adapt monitoring inputs from the application repository and import the
      Jenkins foundation from `infra/jenkins-host/`, preserving useful source
      configuration and history. Keep the application checkout read-only in
      this phase.
- [x] Prepare independent nonprod/PROD resources for the agreed Admin VIPs.
      Resolve v1.2.3 election/lease, selectors, RBAC, hostNetwork port separation
      and LoadBalancer class handling before applying either DaemonSet.
- [x] Review Service ownership against Argo CD inventories. Use reviewed
      environment changes for existing managed Services or separately named
      administrative Services; do not introduce two declarative owners for
      one resource or allow self-healing to undo the intended exposure.
- [x] Write the implementation and recovery runbooks alongside manifests.
      Provide standalone files for substantive operator scripts. Keep new
      reports/plans under `docs/testreports/` and generated data ignored.

### 8.2 — Establish DEV/STAGE Admin VIP

- [x] Deploy its services-only kube-vip and explicit VIP Services. Keep the
      existing API kube-vip and public Traefik/ServiceLB unchanged.
- [x] Expose Argo CD at `.16:8080`, Adminer DEV at `.16:8081` and Adminer
      STAGE at `.16:8082` using the native service protocols and logins.
- [x] Check ordinary readiness, one agreed VIP owner, the separate service
      lease, correct Service status and no ServiceLB administrative workloads.
      Confirm browser access from a Tailscale client without a tunnel or
      manual port-forward. This is a functional check, not a failover test.

Local readiness/browser/ownership checks passed. The operator confirmed external
Tailscale browser access and passwords on 2026-10-22; failover is untested.

### 8.3 — Install DEV/STAGE monitoring

- [x] Adapt source `monitoring/` values, monitors, dashboards and alert rules
      to actual K3s labels/namespaces and `local-path` storage. Pin the chart
      and images as appropriate; size CPU/RAM, retention and PVCs for this
      single-host lab before installation. Do not copy kind `standard` storage.
- [x] Install its own Prometheus, Alertmanager, Grafana, operator,
      kube-state-metrics and Node Exporter. Provision credentials outside Git.
- [x] Expose only the agreed browser ports: Grafana `.16:3000`, Prometheus
      `.16:9090`, Alertmanager `.16:9093`. Keep exporter/operator endpoints
      internal. Configure native URLs/redirects for IP-and-port access.
- [x] Confirm loaded dashboards, useful node/application/Argo CD/Traefik
      metrics and alerts identify DEV/STAGE correctly. Agree any external
      alert destination before enabling delivery; do not treat API acceptance
      as proof of notification receipt. Synthetic notification tests are not
      a gate for this implementation increment.

### 8.4 — Establish PROD administration and monitoring

- [x] Apply the independent services-only kube-vip and explicit `.17` Services
      after nonprod functional readiness. Keep API VIP `.12` and public ingress
      unchanged; do not share election or monitoring state across clusters.
- [x] Expose Argo CD `.17:8080`, Adminer PROD `.17:8081`, Grafana `.17:3000`,
      Prometheus `.17:9090` and Alertmanager `.17:9093`.
- [x] Install separate monitoring with explicit PROD retention/storage,
      credentials, datasource identity and PROD alert rules. Confirm no
      DEV/STAGE application selectors were copied into PROD configuration.
- [x] Confirm ordinary readiness and browser access through Tailscale;
      record that VIP failover and local-volume recovery remain untested.

Local readiness/browser/ownership checks passed. The operator confirmed external
Tailscale browser access and passwords on 2026-10-22; failover is untested.

### 8.5 — Install the Jenkins foundation in DEV/STAGE

- [x] Deploy one controller in namespace `jenkins`, with its own persistent
      `JENKINS_HOME` PVC, explicit resource budget and no controller executors.
      Reuse the proof-of-concept image/plugin/JCasC configuration wherever
      compatible. Keep existing Jenkins and its data unchanged during setup.
- [x] Make the controller image available to K3s using the source Dockerfile
      and image/plugin locks; the proof of concept's host-local image tag is
      not a pullable cluster image. Record the reviewed registry image digest
      and required pull credentials without changing Jenkins core/plugins
      merely as part of the deployment migration.
- [x] Expose native HTTP/login at `http://192.168.77.16:8085`, with the native
      Jenkins base URL set accordingly. Do not create a PROD controller.
- [x] Keep build agents, trusted publisher migration, build cache and
      operational jobs for Phase 9. Do not activate polling, scheduled jobs,
      publication or promotion imported by JCasC/Job DSL during foundation
      startup; make this disabled initial state explicit and reviewable.
      Initially load only controller/login configuration and defer
      job-generating DSL and its publishing credentials until Phase 9.
- [x] Confirm controller/PVC readiness and private login, and document the
      exact reusable source, deferred components and Phase 9 migration inputs.

### 8.6 — Record functional completion and boundaries

- [x] Record the actual address/port/protocol map and ordinary readiness for
      both clusters, Adminer environments, monitoring and Jenkins foundation.
      Confirm no new public administrative NAT/ingress routes were introduced
      and check the new interfaces are not reachable from the public origin.
- [x] Record GitOps/application health after the changes; preserve existing
      database PVCs, credentials, API VIPs and the public application path.
- [x] Publish the Phase 8 report with completed items and remaining limits.
      Do not claim tested failover, recovery or notification delivery. No
      stress, node-failure, reboot or failover tests are required in this phase.

**Pass:** both clusters have their own useful monitoring and permanent
IP-and-port administrative access through Tailscale; the nonprod Jenkins
foundation is reachable with persistent storage. Working CI, failover tests,
VM 100 retirement and legacy NAT removal are outside this phase. The operator
confirmed external Tailscale browser access and passwords; Phase 8 is closed.
