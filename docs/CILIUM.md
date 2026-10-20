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
