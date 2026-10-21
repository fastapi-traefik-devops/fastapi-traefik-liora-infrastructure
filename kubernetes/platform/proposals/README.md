# Pending implementation decisions

## Admin VIP status ownership guard

Status: **proposal only; not deployed or included in a kustomization**.

On NONPROD K3s `v1.36.5+k3s1`, an administrative LoadBalancer class prevents
ServiceLB DaemonSets, but ServiceLB's EndpointSlice handler still queues the
Service. `updateStatus()` checks only its type, then replaces its status with
IPs derived from nonexistent ServiceLB Pods. This clears kube-vip's VIP and
breaks kube-proxy routing. Observed `UnAvailableLoadBalancer` events identify
`service-lb-controller`; monitoring Services became Pending despite Ready
backends. Argo/Adminer initially worked before any new backend readiness event.
Do not consider them immune to the same issue.

References: pinned K3s source
[`onChangeEndpointSlice` and `updateStatus`](https://github.com/k3s-io/k3s/blob/v1.36.5%2Bk3s1/pkg/cloudprovider/servicelb.go).
The inspected master source also lacks a class guard in `updateStatus`; no
verified fixed release was selected. Do not promise an ordinary upgrade fixes it.

`admin-status-ownership.yaml` is a narrowly scoped native admission policy.
It allows only `system:serviceaccount:kube-system:kube-vip-admin` to update
`services/status` for class `liora.aprt.info/admin-vip`. It does not affect
other Services, Pods, API VIP election, public ingress, network traffic or
Tailscale permissions, and requires no new controller Pods. Server dry-run passed
on NONPROD; behavior, controller retries and actual CEL admission enforcement
remain untested because the policy has not been deployed.

Trade-offs: it prevents the conflicting writes rather than fixing K3s. ServiceLB
will still attempt/retry its invalid updates and may emit denial logs. Manual
admin-Service status writes are also denied; an operator can remove the exact
binding to undo the guard. Initial adoption must explicitly reconcile status
through kube-vip, verify access and watch for retries before considering PROD.
Do not restart nodes or stop public ServiceLB as an implicit workaround.

This adds an implementation mechanism beyond the reviewed class-only isolation.
Obtain the operator's choice before applying it. Alternatives require a separate
review of K3s/ServiceLB or public Traefik ownership; those changes are not part
of the currently deployed increment.
