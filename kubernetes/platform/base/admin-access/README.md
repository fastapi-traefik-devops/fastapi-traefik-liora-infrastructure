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

**Deployment hold:** K3s v1.36.5+k3s1's separate EndpointSlice status worker still
ignores the class and clears VIP status. This was observed on NONPROD monitoring
Services and breaks routing despite healthy backends. Therefore class handling
alone does not establish controller isolation. See
[the pending ownership proposal](../../proposals/README.md). Do not deploy this
configuration to PROD or claim stable administrative access before resolving it.

NONPROD has this DaemonSet and the Argo/Adminer private Services applied. Initial
Argo browser login passed, but backend changes can trigger the same status bug.
PROD is prepared only. No public ingress, API VIP or existing ServiceLB settings
were changed. Failover and storage HA are not claimed.
