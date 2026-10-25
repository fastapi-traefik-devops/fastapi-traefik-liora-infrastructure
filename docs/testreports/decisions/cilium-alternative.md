# Historical network design alternative — Cilium

Consolidated on 2026-10-24. This discussion is historical context, not an
installation requirement. The repository provisions the K3s default Flannel
VXLAN network and embedded network-policy controller. No Cilium installation
or network-policy-controller replacement is configured.

Repository evidence: [first server](../../../infrastructure/k3s-cluster/ansible/10_first_server.yml),
[joining servers](../../../infrastructure/k3s-cluster/ansible/30_join_servers.yml).
Neither configuration disables Flannel or the embedded policy controller.
The embedded controller uses kube-router's network-policy library; this does
not install the rest of kube-router. Upstream references:
[K3s default network options](https://docs.k3s.io/networking/basic-network-options)
and [network-policy controller](https://docs.k3s.io/networking/networking-services#network-policy-controller).

Current architecture: [cluster networking](../../ARCHITECTURE.md#cluster-networking).

## Original discussion

# Cilium alternative

## Current cluster network

Primary cluster:

```text
Flannel
+ K3s embedded network-policy controller
```

This is the current, simple baseline for the cluster.

## Move to Cilium when a requirement exists

Examples:

- eBPF service dataplane;
- Hubble observability;
- richer NetworkPolicy;
- BGP control plane;
- kube-proxy replacement;
- advanced multi-cluster networking.

## Do not treat Cilium as a required K3s upgrade

It is a different networking design.

A good learning progression:

```text
Flannel
  ↓ understand Pod/Service/Gateway/LB
Cilium in a second cluster
  ↓ compare packet path and policy
```

Do not change CNI at the same time as troubleshooting an ingress or LoadBalancer
problem.
