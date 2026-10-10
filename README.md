# Proxmox + HA K3s lab

A production-shaped, learning-oriented K3s cluster on Proxmox.

## Target lab

```text
Public IP: 151.115.96.5
LAN:       192.168.77.0/24
Proxmox:   192.168.77.1

K3s:
  k3s-01   192.168.77.201
  k3s-02   192.168.77.202
  k3s-03   192.168.77.203

Kubernetes API VIP:
  192.168.77.10   (kube-vip, ARP)

Optional MetalLB pool:
  192.168.77.50-192.168.77.59

Application domain:
  liora-fastapi.aprt.info
```

All three K3s nodes are `server` nodes. They run the control plane, embedded etcd,
and normal workloads.

## Primary design

```text
Internet
  |
  | 151.115.96.5:80/443
  v
Proxmox nftables DNAT                  LAB edge
  |
  | -> 192.168.77.201:80/443
  v
K3s ServiceLB
  |
  v
Traefik
  |
  +--> Gateway API (primary)
  |       |
  |       v
  |     HTTPRoute
  |
  +--> Ingress (comparison)
          |
          v
      ClusterIP Service
          |
          v
       Pods :8080
```

Control plane:

```text
kubectl / joining nodes
        |
        v
192.168.77.10:6443
     kube-vip
        |
   +----+----+
   |    |    |
 .201 .202 .203
   \    |    /
    embedded etcd
```

## Important architectural choice

The primary scenario intentionally keeps **K3s ServiceLB**. MetalLB is supplied as
a later migration scenario so the difference between the two mechanisms can be
observed directly.

## Start here

Read `FINAL_MANUAL.md`.

The exact commands and file order for every scenario are in:

- `FINAL_MANUAL.md`
- `docs/SCENARIOS.md`

## Repository layout

```text
.
├── infrastructure/
│   └── opentofu/             # Proxmox VM IaC
├── ansible/                  # automated node preparation + HA K3s
├── kubernetes/
│   ├── kube-vip/
│   ├── traefik/
│   ├── apps/
│   ├── gateway/
│   ├── ingress/
│   ├── tls/
│   ├── metallb-optional/
│   └── gitops/
├── edge/
│   ├── nftables/             # primary lab edge
│   └── haproxy/              # production-shaped edge
├── scripts/
│   ├── proxmox/
│   └── manual/
└── docs/
```

## Security

No real API token, K3s token, Cloudflare token, password, or private key is stored
in this repository. Files containing real secrets are intentionally ignored by Git.
