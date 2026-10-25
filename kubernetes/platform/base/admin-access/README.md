# Administrative VIP controller

Independent services-only kube-vip v1.2.3; global ARP service election uses
`kube-system/liora-admin-services`, not the API DaemonSet's `plndr-cp-lock`.
`svc_election=false` selects one leader for all shared-IP Services. Metrics use
2113 instead of API kube-vip's 2112. Dedicated names, selectors and RBAC avoid
adopting existing controller objects. Node selectors match actual K3s labels.

Every administrative Service explicitly selects class `liora.aprt.info/admin-vip`,
sets its assigned IP annotation, disables NodePort allocation and uses Cluster
traffic policy. kube-vip rejects classless/foreign Services. K3s's cloud service
controller does not create ServiceLB Pods for these Services.

## Required K3s status ownership guard

K3s v1.36.5+k3s1's separate EndpointSlice status worker ignores the class and
clears foreign VIP status. `status-ownership.yaml` is the operator-approved
compatibility guard: only this service account may update administrative-class
Service status. Other classes, API VIPs, workload admission and network access
are unaffected. The binding is included in this kustomization; apply it before
creating VIP Services. See the [decision record](../../../../docs/testreports/decisions/admin-vip-status-ownership.md).

NONPROD admission and direct status/routing checks passed after enforcement.
ServiceLB creates no administrative DaemonSets, but still retries its rejected
status writes and may log denials. This prevents corruption rather than fixing
K3s. Do not claim a class filter alone provides isolation, and do not disable
public ServiceLB as a workaround. Ordinary readiness checks do not establish
failover or storage HA.
