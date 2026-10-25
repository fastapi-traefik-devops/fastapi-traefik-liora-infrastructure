# K3s fixed node memory — 2026-10-25

## Reason and configuration

The owner reported build/application failures associated with insufficient node
memory and requested 8 GiB per node without ballooning. Code inspection found
the shared six-VM Terraform resource used 8192 MiB dedicated memory with a
2048 MiB floating-memory setting. This allowed the ballooned configuration to
remain inconsistent with the required fixed-memory model.

The module now configures all six nodes with `memory.dedicated = 8192` and
`memory.floating = 0`. The pinned bpg/proxmox 0.111.1 provider documents zero
floating memory as disabling the ballooning device. The `memory_min_mb` input
is removed; validation rejects `memory_mb` values other than 8192. Existing
private tfvars must remove the retired assignment before their next plan.

| Cluster | VM IDs | RAM per node | Cluster RAM |
| --- | --- | --- | --- |
| NONPROD | 201–203 | 8 GiB fixed | 24 GiB |
| PROD | 211–213 | 8 GiB fixed | 24 GiB |

Reserve 48 GiB for cluster VMs plus other VMs and Proxmox overhead. Management
VM 200, router VM 250, edge VM 240 and the base VM template are unchanged.

## Documentation

The module README/example, VM provisioning runbook, architecture, implementation
plan and topology diagram use the fixed-memory policy. The runbook checks the
Proxmox setting, guest memory and Kubernetes capacity/allocatable after deployment;
allocatable is expected to be below physical guest memory. Historical incident
reports retain the original configuration and observations.

## Local validation

Using checksum-verified Terraform 1.9.8 and the module's pinned provider:

- Recursive `terraform fmt -check` passed.
- `terraform validate` passed.
- Two mocked plan checks passed: exact six-node inventory with 8192 MiB and zero
  floating memory; rejection of a 2048 MiB override.
- Mocked plans use a visibly fake public-key fixture and example-only provider
  inputs. They do not contact Proxmox or consume private operator credentials.
- Diagram XML and local documentation references were checked; the topology
  page was rendered with the diagrams.net graph engine to inspect the added
  memory labels.

Backend initialization was disabled. Provider cache/tooling and the generated
ignored dependency lock are local validation artifacts, not infrastructure state.
No Terraform state, private tfvars, recovery credentials or existing VM was
modified. No Terraform apply, cluster change, node restart or Git push was run.

These results verify provisioning configuration, not live guest memory or
post-restart kubelet capacity. Existing-node reconciliation belongs in an
explicitly planned maintenance operation with the original state preserved.
