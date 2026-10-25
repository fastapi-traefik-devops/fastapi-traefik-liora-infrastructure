# Infrastructure cost estimate

**Estimate date:** 25 October 2026. **Region:** Europe. **Currency:** EUR, excluding VAT.

This is a planning estimate for the infrastructure in [ARCHITECTURE.md](docs/ARCHITECTURE.md), not a quotation or a reconstruction of current invoices. All options retain **one physical Proxmox host**, two K3s clusters and the existing application/platform services. Capacity and support vary; the maximum option is not a spending ceiling or a high-availability design.

## 1. Budget summary

| Cost | Minimum | Medium — recommended | Maximum — capacity and support |
| --- | ---: | ---: | ---: |
| Recurring monthly equivalent | **€181.29** | **€356.93** | **€630.41** |
| Recurring annual equivalent | €2,175.48 | €4,283.16 | €7,564.92 |
| Server setup / commitment fee | €154.99 | €129.00 | €449.99 |
| First year, including setup | **€2,330.47** | **€4,412.16** | **€8,014.91** |
| Monthly budget with 15% reserve, rounded up | **€209** | **€411** | **€725** |

Annual equivalents use the rounded monthly lines below. Annual subscriptions and domain renewal may be paid upfront. Setup is charged once; the 15% reserve is a planning allowance, not a supplier charge. Prices, stock, renewal terms and configuration must be checked at purchase.

**Recommendation:** budget about **€415/month plus setup** for the medium option. It gives substantially more RAM and CPU headroom than the current VM allocations, mirrored NVMe capacity and a Proxmox support subscription. Human system administration is a separate cost.

## 2. What the existing architecture requires

| Existing component | Quantity | Configured RAM | Configured vCPU |
| --- | ---: | ---: | ---: |
| K3s servers, NONPROD and PROD | 6 | 6 × 8 GiB = 48 GiB, fixed; no ballooning | 6 × 2 = 12 |
| Management VM 200 | 1 | 2 GiB | 2 |
| HAProxy VM 240 | 1 | 1 GiB | 1 |
| Tailscale / backup-monitoring VM 250 | 1 | 1 GiB | 1 |
| **VM allocation total** | **9** | **52 GiB** | **16** |

The figures describe repository defaults and procedures, not a live host inventory. Sources: [K3s Terraform](infrastructure/k3s-cluster/terraform/variables.tf), [management VM](runbooks/04-create-management-vm-200.md), [HAProxy Terraform](edge/haproxy/terraform/main.tf), [Tailscale Terraform](edge/tailscale/terraform/main.tf).

Allow additional RAM for Proxmox, ZFS, caches and temporary recovery workloads. A 32 GB server cannot hold this allocation. A 64 GB server is a tight minimum; 128 GB is the preferred starting point. vCPUs are not physical cores, and concurrent DinD builds compete with databases and monitoring on the same host.

Use SSD/NVMe storage with redundancy. Advertised drive totals are raw capacity: two 960 GB drives provide approximately 960 GB before filesystem overhead when mirrored. Thin-provisioned VM disk sizes are not actual usage. Before purchase, inventory allocated/used storage, Jenkins artifacts/cache, monitoring retention, database growth and temporary restoration space. Keep at least 20% of the selected usable pool free. The minimum option is conditional on fitting that storage budget.

One public IPv4 and a local Proxmox private bridge/NAT support this topology. Do not buy nine cloud servers, a managed load balancer or an inter-host private-network option for these nine VMs.

## 3. Dedicated-server comparison

Published European prices below exclude VAT. These are rental candidates, not reservations. Install a supported Proxmox release using the provider's current image or rescue/remote-console procedure; verify exact hardware and installation access before ordering.

| Provider / candidate | CPU | RAM | Drives / approximate redundant usable capacity | Server/month | Setup | Assessment |
| --- | --- | ---: | --- | ---: | ---: | --- |
| Hetzner AX42-1 | Ryzen 7 PRO 8700GE | 64 GB | 2 × 512 GB NVMe / 512 GB mirror | €97.30 + €1.70 IPv4 = **€99.00** | €49.00 | Lower-cost alternative; RAM and storage headroom are limited |
| Hetzner AX102-1 | Ryzen 9 7950X3D | 128 GB | 2 × 1.92 TB NVMe / 1.92 TB mirror | €257.30 + €1.70 IPv4 = **€259.00** | €129.00 | Medium scenario; good CPU/RAM balance |
| OVHcloud ADVANCE-2, Gen 2024 | EPYC 4344P, 8 cores | 64 GB | 2 × 960 GB NVMe / 960 GB mirror | **€154.99** | €154.99 | Minimum scenario, subject to stock and capacity checks |
| OVHcloud ADVANCE-2, Gen 2026 + 128 GB option | EPYC 4345P, 8 cores | 128 GB | 2 × 960 GB NVMe / 960 GB mirror | €199.99 + €92 = **€291.99** | Confirm configured quote | Alternative to medium; smaller disk pool |
| Scaleway EM-A410X-SSD | Xeon E5-1650, 6 cores / 12 threads | 64 GB | 2 × 1.02 TB SATA SSD / 1.02 TB mirror | **€54.99** | €54.99 commitment | Cheapest quoted candidate, but older CPU and DDR3 make it a weaker fit for concurrent CI |
| Scaleway EM-L520E-NVMe | EPYC 8124P, 16 cores / 32 threads | 128 GB | 4 × 3.84 TB NVMe / 7.68 TB as two mirrored pairs | **€449.99** | €449.99 commitment | Maximum scenario; greater storage capacity and modern CPU |

Hetzner rates: [June 2026 tariff](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), [IPv4 charge](https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/), [AX42 configuration](https://www.hetzner.com/dedicated-rootserver/ax42/configurator/), [AX102 specifications](https://www.hetzner.com/dedicated-rootserver/ax102/). The selected standard 1 Gbit/s Hetzner connection has unlimited traffic; separately priced faster connections have different terms. Limited-stock LTD offers are excluded from the budget.

OVHcloud rates: [current Advance range](https://www.ovhcloud.com/en-ie/bare-metal/advance/) and [new-order H2 2026 tariff](https://blog.ovhcloud.com/en/posts/dedicated-servers-pricing-update-h2-2026/). Use the current new-order prices, not earlier configurator or renewal prices. Budget one included primary IPv4; additional IPs and optional network upgrades are excluded. Confirm setup charges for configured RAM/storage upgrades.

Scaleway rates/specifications: [Elastic Metal pricing](https://www.scaleway.com/en/pricing/elastic-metal/) and [2026 price update](https://www.scaleway.com/en/blog/a-transparent-update-on-scaleway-pricing/). Monthly billing has a commitment fee equal to one month's rent; hourly billing has different economics. A [default public IPv4 is provided](https://www.scaleway.com/en/docs/elastic-metal/reference-content/elastic-metal-networking/); a paid flexible IP is unnecessary here. Provider private networking is also unnecessary for this single-host design. Scaleway publishes [Proxmox installation guidance](https://www.scaleway.com/en/docs/tutorials/setup-elastic-metal-proxmox-cluster-with-private-networks/); its multi-host example is not a requirement for this estimate.

Hardware rental includes the provider's power, rack and base network service. It does not include application administration or database recovery work. Proxmox subscriptions support Proxmox, not the entire application stack.

## 4. Scenario assumptions and calculation

All scenarios assume three administrators/developers, three application environments, existing self-hosted Jenkins CI, one public IPv4, traffic within the chosen included connection and no paid hosted build runners. Approximate monthly outbound application traffic is 0.5 / 1 / 3 TB; these are sizing assumptions, not measured demand or load-test results.

| Monthly expense | Minimum | Medium | Maximum |
| --- | ---: | ---: | ---: |
| Dedicated server, including primary IPv4 | OVHcloud €154.99 | Hetzner €259.00 | Scaleway €449.99 |
| Proxmox subscription, one physical CPU socket | No subscription: €0.00 | Standard, €550/year: €45.83 | Premium, €1,100/year: €91.67 |
| Tailscale Standard, 3 × $8/month | €22.80 | €22.80 | €22.80 |
| GitHub organization | Free: €0.00 | Team, 3 × $4/month: €11.40 | Team, 3 × $4/month: €11.40 |
| R2 storage allowance, including small rounding margin | 50 GB: €1.00 | 250 GB: €4.00 | 1,000 GB: €15.00 |
| One parent domain renewal allowance, €30/year | €2.50 | €2.50 | €2.50 |
| Cloudflare DNS and Access Free; Slack Free; GHCR | €0.00 | €0.00 | €0.00 |
| UptimeRobot external domain/API monitoring | Free: €0.00 | Solo, $12/month annually: €11.40 | Team, $39/month annually: €37.05 |
| **Monthly equivalent total** | **€181.29** | **€356.93** | **€630.41** |

USD prices use the explicit **planning conversion $1 = €0.95**. This is a budget assumption, not a current exchange-rate quotation; card/FX charges and rate changes come from the reserve. No current subscription invoices were supplied. Selected paid plans are proposed budget choices, not claims about existing billing.

- **Minimum:** existing VM allocation, constrained build concurrency and storage retention, no Proxmox vendor subscription. It is the lowest proposed operating profile, not the cheapest server in the market. The cheaper Hetzner/Scaleway candidates above need stricter storage/CPU qualification.
- **Medium:** 128 GB RAM, faster CI capacity, 1.92 TB mirrored disk pool, Proxmox Standard and GitHub Team. This is the recommended balance.
- **Maximum:** 128 GB RAM, substantially larger redundant NVMe pool and Proxmox Premium. Additional capacity supports growth and artifact retention; it does not remove the single-host failure domain. It does not assume a new managed-support contract.

[Proxmox subscriptions](https://www.proxmox.com/en/products/proxmox-virtual-environment/pricing) are billed per physical CPU socket per year, not per core, VM or K3s node. These examples assume one socket. [Tailscale Standard](https://tailscale.com/pricing) is $8/user/month; budget a business team plan rather than assuming eligibility for Personal. [GitHub Team](https://github.com/pricing) advertises $4/user/month for the first 12 months: confirm renewal pricing before projecting later years. GitHub Free is a cost option only where its repository controls meet the required workflow.

## 5. Other services and possible charges

| Service / component | Treatment in this estimate |
| --- | --- |
| Cloudflare DNS / proxy | Free zone plan assumed. Pro/Business plans are optional; they are not required merely to host the three subdomains. |
| Cloudflare Access | Free plan assumed for this three-person team; published limit is 50 users. Paid support or additional requirements change this choice. |
| Domain registration | One registered parent domain, `aprt.info`; its three application subdomains do not require three registrations. €30/year is an allowance because registrar/renewal invoice is unknown. |
| R2 `liora-backup` | Usage-billed storage and requests; includes PostgreSQL base backups, WAL and native etcd snapshots. No separate charge per environment/bucket prefix. |
| GitHub Actions | Only GitHub-hosted validation consumes Actions allowances; Jenkins builds run on the rented host. Assume no billable overage. Review organization billing if validation minutes/artifacts grow. |
| GHCR container images | Container-registry storage and bandwidth are currently free under GitHub's published policy. Do not apply unrelated Packages tariffs to GHCR. |
| Slack | Existing incoming-webhook alert delivery budgeted on Free. Paid message history, organization controls or support are optional; not included. |
| Certificates | Let's Encrypt certificates and self-hosted cert-manager have no subscription charge. |
| Self-hosted software | K3s, CNPG, Barman Cloud Plugin, Jenkins, Argo CD, HAProxy, Traefik, Prometheus, Alertmanager, Grafana, Ansible and Terraform tooling add no assumed license charge for this use; their resource use is included in the server. |
| Private recovery kit | Owner-provided encrypted off-host storage assumed. No new paid storage subscription is included; add its incremental cost if one is needed. |
| UptimeRobot | External HTTPS and API availability checks; Free / Solo / Team are included in the scenario totals. Account setup and monitor activation are separate operational work. |
| SMTP, managed logging, additional support | No paid service is assumed. Obtain separate prices if adopted; these are not hidden dependencies of the total. |

Sources: [Cloudflare plans and Access pricing](https://www.cloudflare.com/plans/), [GHCR billing policy](https://docs.github.com/en/billing/concepts/product-billing/github-packages#free-use-of-github-packages), [Slack plans](https://slack.com/pricing). Free plans have feature, history and support limits; €0 does not imply equivalent support to a paid plan.

## 6. External monitoring with UptimeRobot

Budget six external HTTP(S) monitors: one application page and one API health endpoint for each of `liora.aprt.info`, `dev.liora.aprt.info` and `stage.liora.aprt.info`. This detects failures outside the host, including public routing and application reachability; internal Prometheus monitoring remains in place. Select each API URL and expected status/body from the deployed application rather than treating any HTTP response as success.

| Scenario | Plan | Included monitors / interval | Published price | Budget in EUR |
| --- | --- | --- | --- | --- |
| Minimum | Free | 50 / 5 minutes | $0 | €0 |
| Medium | Solo | 10 / 60 seconds | $144/year, equivalent to $12/month | €136.80/year; €11.40/month |
| Maximum | Team | 100 / 30 seconds; 3 seats | $468/year, equivalent to $39/month | €444.60/year; €37.05/month |

Paid figures assume annual prepayment and the same $1 = €0.95 planning conversion. Month-to-month prices are $13 for Solo and $46 for Team: €12.35 and €43.70/month respectively. SMS/voice credits and extra seats are excluded. Sources: [UptimeRobot pricing](https://uptimerobot.com/pricing/) and [Free plan commercial-use eligibility](https://help.uptimerobot.com/en/articles/11604710-who-should-use-uptimerobot-s-free-plan).

DEV/STAGE Cloudflare Access requires an authenticated monitoring request. Confirm the selected plan supports the required request headers and use a scoped service token stored privately. Do not disable Access, expose administrative endpoints, or count a redirect to an authentication page as application health. Six monitors fit the Solo allowance; more API checks may require a higher tier. Confirm notification integrations before purchase; do not assume Free has the same alert delivery options as paid plans.

This is a cost provision, not a claim that UptimeRobot monitors are already configured. It adds no cluster-side agent or paid managed database dependency.

## 7. R2 calculation and growth

Use the Standard storage class. Published [R2 pricing](https://developers.cloudflare.com/r2/pricing/) is $0.015/GB-month, $4.50/million Class A operations and $0.36/million Class B operations. The monthly free allowance is 10 GB-months, 1 million Class A and 10 million Class B operations. Direct R2 internet egress is free. Allowances are shared at account level; billing rounds applicable quantities.

For this estimate, assume the account allowance is available and requests stay within the free operation allowances:

```text
Estimated storage EUR/month = max(average GB-months - 10, 0) × $0.015 × 0.95
50 GB:    €0.57 → budget €1/month
250 GB:   €3.42 → budget €4/month
1,000 GB: €14.11 → budget €15/month
Add billable request charges if the account exceeds its allowances.
```

These are average stored volumes across full backups, required recovery-window anchors, WAL and etcd snapshots, not logical database sizes. Retention remains DEV/STAGE 7 days and PROD 14 days for PostgreSQL, independently of etcd retention. Do not shorten recovery windows or delete required WAL to meet a cost assumption.

The recent coordinator metric reported approximately 0.114 GB in R2; this point-in-time observation is not an invoice or a prediction of steady-state backup volume. The 10 GiB monitoring warning is informational, not a storage quota. Recalculate from measured GB-months and requests after a complete retention window and after significant workload growth.

## 8. Before accepting a supplier quote

- [ ] Confirm server stock, EU location, net price, renewal price, minimum term and setup charge.
- [ ] Confirm physical socket count, ECC specification, drive endurance and hardware replacement terms.
- [ ] Confirm current Proxmox installation/remote-console access and NIC/storage compatibility.
- [ ] Inventory actual VM/PVC usage and agree usable mirrored capacity, growth and free-space margin.
- [ ] Confirm included primary IPv4, bandwidth, traffic policy and DDoS terms; add no extra IPs without a need.
- [ ] Confirm the selected Tailscale, GitHub, Cloudflare, Slack and UptimeRobot plans meet operational requirements.
- [ ] Confirm registrar renewal, existing paid subscriptions and account-wide free-tier consumption.
- [ ] Add VAT where applicable and obtain a separate operations/support labour estimate.

Excluded: implementation labour, ongoing operator/on-call labour, client devices/internet, taxes, migration overlap, dedicated hardware purchase/depreciation and services not selected above. Renting a host replaces its power/rack costs in this calculation; do not add those again. Standard and maximum subscriptions do not guarantee application RTO or automatic recovery. Every scenario retains the shared physical-host outage risk of the current architecture.
