# Infrastructure architecture

This document defines the desired architecture of the Liora platform.
Editable infrastructure diagrams: [project-schemes.drawio](project-schemes.drawio).
Operating procedures belong in the [operator manuals](../runbooks/README.md).
Implementation order, migration history and execution results belong in the
[implementation plan](testreports/IMPLEMENTATION_PLAN.md) and [phase reports](testreports/README.md).

## Platform topology

One Proxmox host runs two independent, three-server K3s clusters. DEV and STAGE
share the NONPROD cluster and have separate namespaces, databases and Secrets.
PROD has its own cluster, data and administrative configuration.

| Component | VM IDs | Private addresses |
| --- | --- | --- |
| Proxmox gateway | Host | `192.168.77.1` |
| Management | 200 | `192.168.77.200` |
| Public application edge | 240 | `192.168.77.240` |
| Tailscale subnet router | 250 | `192.168.77.250` |
| NONPROD K3s servers | 201–203 | `192.168.77.201`–`192.168.77.203` |
| PROD K3s servers | 211–213 | `192.168.77.211`–`192.168.77.213` |

The private network is `192.168.77.0/24` on Proxmox `vnet77`. VM addresses are
static. DHCP allocation excludes static VM addresses and all floating addresses.
Proxmox provides outbound NAT. The public IPv4 address is a
recovery/configuration input.

Terraform manages infrastructure resources; Ansible configures guest operating
systems, K3s and the edge. VM 200 is the operator host for these tools and holds
separate NONPROD and PROD kubeconfigs. Each infrastructure module has its own
state and recovery procedure. Credentials, private keys and state stay outside Git.

Each of the six K3s server VMs has 8 GiB fixed RAM with ballooning disabled
(24 GiB per cluster, 48 GiB total). Each cluster uses embedded etcd across its
three server nodes. CPU, workload resources, replicas and storage requests are
explicit configuration within the resource budget of the single Proxmox host.

## Cluster networking

Both clusters use the K3s default Flannel CNI with its VXLAN backend and the
embedded Kubernetes NetworkPolicy controller based on kube-router's netpol
library. Cilium and a separate kube-router deployment are not installed.
Namespace-scoped NetworkPolicy resources constrain Jenkins controller, CI,
publisher and observer traffic. There is no cluster-wide enforced default-deny
policy. Public Services, API VIPs and Admin VIP ownership remain separate from
the Pod network.

Configuration sources: [first-server bootstrap](../infrastructure/k3s-cluster/ansible/10_first_server.yml)
and [joining-server bootstrap](../infrastructure/k3s-cluster/ansible/30_join_servers.yml)
retain the defaults without Flannel or policy-controller disable flags.
[K3s network options](https://docs.k3s.io/networking/basic-network-options) and
[policy implementation](https://docs.k3s.io/networking/networking-services#network-policy-controller)
define those defaults.

## Address roles and traffic ownership

| Purpose | NONPROD | PROD |
| --- | --- | --- |
| Kubernetes API | `192.168.77.11:6443` | `192.168.77.12:6443` |
| Public application ingress | Traefik ServiceLB nodes `.201`–`.203` | Traefik ServiceLB nodes `.211`–`.213` |
| Private administrative Services | `192.168.77.16` | `192.168.77.17` |

API, public ingress and administrative addresses have separate roles and
controller ownership. HAProxy sends application traffic to each cluster's
Traefik ServiceLB node addresses. Separate public-ingress VIPs are not part of
this design; API and Admin VIPs are never ingress backends.

API kube-vip instances serve cluster control-plane access. Separate
services-only kube-vip instances serve administrative Services. K3s ServiceLB
owns the public Traefik Service; neither an API nor an Admin VIP is reused for it.
Each LoadBalancer Service has one controller responsible for its status and
address advertisement. LoadBalancer classes and admission rules enforce that
ownership without competing ServiceLB updates.

## Public application access

| Environment | Cluster / namespace | Application URL |
| --- | --- | --- |
| DEV | NONPROD / `app-dev` | `https://dev.liora.aprt.info` |
| STAGE | NONPROD / `app-stage` | `https://stage.liora.aprt.info` |
| PROD | PROD / `app-prod` | `https://liora.aprt.info` |

Cloudflare manages public DNS. DEV and STAGE use Cloudflare protection/Access;
PROD uses DNS-only public-origin access. The origin path is Proxmox public
TCP 80/443 forwarding to HAProxy VM 240, then the selected cluster's Traefik
ServiceLB node pool. HTTP requests redirect to HTTPS. HAProxy routes only
application hostnames and rejects unknown and administrative names.

```mermaid
flowchart LR
  NonprodBrowser[DEV / STAGE browser] --> Cloudflare[Cloudflare protection / Access]
  ProdBrowser[PROD browser] --> Origin[Proxmox public origin]
  Cloudflare --> Origin
  Origin --> Edge[HAProxy VM 240]
  Edge --> NonprodNodes[NONPROD nodes .201–.203]
  Edge --> ProdNodes[PROD nodes .211–.213]
  NonprodNodes --> NonprodTraefik[NONPROD Traefik]
  ProdNodes --> ProdTraefik[PROD Traefik]
  NonprodTraefik --> NonprodApps[DEV / STAGE application Services]
  ProdTraefik --> ProdApp[PROD application Services]
```

HAProxy passes TLS through using SNI. Traefik terminates origin HTTPS using
certificates managed inside its cluster. DEV/STAGE Access restrictions apply
at the Cloudflare edge; the direct-origin path is not restricted to Cloudflare.

### Certificate lifecycle

Each cluster has its own cert-manager installation and issuer configuration.
Let's Encrypt issues application certificates through ACME DNS-01 validation.
cert-manager creates the required TXT records through the Cloudflare DNS API
and renews certificates into the environment's TLS Secret. Issuer solvers select
only `dev.liora.aprt.info`, `stage.liora.aprt.info` and `liora.aprt.info`; unrelated
subdomains and application routing records remain outside this lifecycle.

Cloudflare credentials are scoped to the required zone and permissions. Private
recovery inputs provision those credentials into Kubernetes. Each TLS Secret
has one certificate-management owner. Certificate issuance and renewal are
cluster-local.

## Private administrative access

Trusted administrators access `192.168.77.0/24` through Tailscale VM 250.
Administrative browser access uses IP and port through each cluster's Admin VIP.
No private ingress, private DNS service, additional reverse proxy, SSH tunnel
or manually started port-forward is required.

```mermaid
flowchart LR
  Browser[Administrator browser] --> Tailscale[Tailscale subnet router .250]
  Tailscale --> Nonprod[Admin VIP 192.168.77.16]
  Tailscale --> Prod[Admin VIP 192.168.77.17]
  Nonprod --> NonprodServices[NONPROD administrative Services]
  Prod --> ProdServices[PROD administrative Services]
```

| Interface | NONPROD | PROD |
| --- | --- | --- |
| Argo CD | `https://192.168.77.16:8080` | `https://192.168.77.17:8080` |
| Grafana | `http://192.168.77.16:3000` | `http://192.168.77.17:3000` |
| Prometheus | `http://192.168.77.16:9090` | `http://192.168.77.17:9090` |
| Alertmanager | `http://192.168.77.16:9093` | `http://192.168.77.17:9093` |
| Jenkins | `http://192.168.77.16:8085` | — |
| Adminer DEV | `http://192.168.77.16:8081` | — |
| Adminer STAGE | `http://192.168.77.16:8082` | — |
| Adminer PROD | — | `http://192.168.77.17:8081` |

Services provide their native HTTP/HTTPS and authentication. Argo CD uses its
native HTTPS endpoint; an IP endpoint does not require a publicly trusted
certificate. Grafana, Jenkins and Argo CD retain native logins. Prometheus and
Alertmanager use their native access model within the trusted private subnet.
No additional SSO, authentication proxy or private certificate authority is part
of this access design.

Tailscale gives trusted administrators subnet access. Additional per-service
ACL/grant restrictions are outside the agreed access model. Administrative
interfaces have no public NAT or HAProxy route. PostgreSQL, Redis, build daemons
and internal exporter endpoints stay on their internal networks. Proxmox and
management SSH use their own addresses outside the Admin VIPs.

### Administrative VIP ownership

Each cluster runs a services-only `kube-vip-admin` DaemonSet with dedicated
selectors, service account and RBAC. All Services sharing an Admin VIP use one
common leader. Its election lease is independent of the API VIP lease.
API and administrative instances have distinct host-network listeners.

Administrative Services explicitly declare their VIP and use LoadBalancer
class `liora.aprt.info/admin-vip`, `externalTrafficPolicy: Cluster` and
`allocateLoadBalancerNodePorts: false`. Only the dedicated administrative
kube-vip identity may update their Service status. API and public ingress
Services belong to their respective controllers.

## Application and database platform

Application configuration uses a shared Kustomize base and separate DEV,
STAGE and PROD overlays. Each environment owns its configuration, runtime
Secrets, database credentials and image digest pair. Frontend and backend
images are immutable and referenced by digest.

CloudNativePG manages a separate PostgreSQL 16 database in each environment.
DEV and STAGE each have one instance; PROD has two instances on different K3s
nodes, using asynchronous streaming replication without synchronous replicas.
Operator and PostgreSQL images are pinned reproducibly. Storage and resource
budgets are environment-specific. The stable application endpoint is `db:5432`;
`app_owner` owns the application database, while `postgres` is an administrative
role with separate connection settings.
Application migrations use the prestart/migration lifecycle and preserve
compatibility with the deployed application.

Database administration uses Adminer through the private Admin VIP endpoints
and native database authentication. Adminer is intentionally retained in DEV,
STAGE and PROD. Direct database intervention uses authenticated administrative
access and an explicit operational change record. Application database ownership remains
separate from the administrative role.

Persistent storage has explicit ownership, retention and recovery rules.
Node-local `local-path` storage does not replicate volume contents. Database
replication, backups and application replica placement are separate from
control-plane and VIP availability. PROD application scaling and disruption
budgets are environment configuration, independent of the number of K3s servers.

### Backup and recovery

PostgreSQL physical base backups and continuous WAL archiving use the Barman
Cloud Plugin with lz4 compression for both. Data travels directly between each
cluster and the private Cloudflare R2 bucket `liora-backup`, outside the Proxmox
host failure domain. DEV, STAGE and PROD use distinct `dev/`, `stage/` and
`prod/` destinations and `liora-dev`, `liora-stage`, `liora-prod` archive identities.
One S3 credential pair is scoped to the bucket; prefixes separate data but do
not provide credential isolation. Private endpoint/credential inputs stay outside Git.

| Environment | Recovery window | Target RPO | Target RTO |
| --- | --- | --- | --- |
| DEV | 7 days | 1 hour | 4 hours |
| STAGE | 7 days | 1 hour | 4 hours |
| PROD | 14 days | 15 minutes | 1 hour |

These are objectives requiring measured restoration and archive-delivery evidence.
RTO starts with a working K3s cluster and R2 access and ends with a usable restored
application; rebuilding Proxmox/K3s is excluded. Five-minute WAL archive timeout
leaves delivery headroom. Barman recovery-window retention preserves the older
anchor backup and required WAL; independent R2 age-deletion rules are excluded.
A raw copy of a running PVC is not a database backup.

VM 250 runs a recoverable systemd full-backup coordinator daily at 02:00 UTC.
A full cycle runs PROD → STAGE → DEV, starting each only after its predecessor
is terminal. A local lock and durable Kubernetes Lease/session fence serialize
scheduled and manually coordinated cycles across hosts. A definitive failure
alerts and advances without retry. Running/unknown state blocks advancement and
retains intent for explicit inspection/resume. The coordinator has only scoped
Backup access and its named Lease; backup data does not pass through VM 250.
WAL archiving and manual recovery do not depend on that VM's availability.

Per-cluster cert-manager provides the plugin's internal self-signed mutual TLS.
Backup health enters the existing Prometheus/Alertmanager stack: failures,
overdue usable backups, WAL problems and missing telemetry have recovery
notifications. No daily success messages are sent. Aggregate R2 usage is measured
across all object pages and warns above 10 GiB; this is informational, not a quota,
retention-fit guarantee or permission to stop backups/force-delete data.

Isolated PITR exercises restore DEV → STAGE → PROD sequentially, with one
temporary database instance at a time. Included/excluded markers around an
explicit target prove replay of archived WAL beyond a physical base backup.
Restored test clusters cannot archive into or prune the source archive and
never replace live endpoints. Operators repeat the exercise monthly and after
significant backup changes; no automated weekly restore schedule is required.

Native K3s embedded-etcd snapshots also upload directly from all six servers to
`etcd/nonprod/` and `etcd/prod/` in the same private bucket. They use the existing
bucket-scoped S3 pair through a cluster-local `kube-system` Secret. Node schedules
are staggered twice daily in UTC: NONPROD 03:00, 03:02, 03:04 and
15:00, 15:02, 15:04; PROD 03:10, 03:12, 03:14 and 15:10, 15:12, 15:14. This separates normal snapshot load from the
02:00 PostgreSQL cycle. Local retention is five snapshots per node. R2 retention
is 42 snapshot files per cluster prefix across its three servers, approximately
seven days at the normal rate. Native ZIP compression and count-based pruning
are independent of Barman recovery windows and never target PostgreSQL prefixes.

Existing native metrics report snapshot creation/upload failures. VM 250's
existing R2 listing supplies snapshot freshness; Prometheus alerts after 14 hours
without a confirmed snapshot. Existing Alertmanager receivers provide failure
and recovery notifications. No extra scheduler or notification service is used.

The standard disaster-recovery sequence rebuilds infrastructure, deploys
platform/configuration, restores application data, then verifies applications.
Etcd restore is an optional manual route. Etcd snapshots recover Kubernetes
metadata and Secrets, not PVC contents. PostgreSQL backups/WAL cover application
database contents; Jenkins requires its stopped-home archive; other persistent
volumes require separate protection. Current original server tokens are saved once at `recovery/k3s-nonprod-server.token` and
`recovery/k3s-prod-server.token`, mode `0600`. Node identities and capture
metadata are stored separately under `recovery/k3s-identities/`. These inputs
are included in the existing encrypted off-host recovery kit. Snapshot files stay on nodes and
in R2; temporary downloads use private `.local-work/` directories, never
`recovery/`. Old tokens stay available for retained snapshots after rotation. [Etcd operations](operations/ETCD_BACKUPS.md)
defines configuration, retention and failure response.

Recovery procedures cover application data, etcd, infrastructure state,
cluster credentials and the encryption material required by the retained backups. Backup copies and private recovery
inputs stay outside Git.

The recovery kit contains the inputs and procedures needed to recreate the
Proxmox guests, both clusters, GitOps and platform services, then restore data.
Jenkins recovery includes controller state, credential encryption material,
users, jobs and retained history. Application/database credentials and registry
access are recoverable independently of an application deployment.

## GitOps ownership

Each cluster has its own Argo CD installation, root Application and AppProject.
NONPROD manages DEV/STAGE; PROD manages PROD. Each controller deploys to its
local Kubernetes API and reads the infrastructure repository.

Argo CD automatically reconciles approved Git state and repairs drift.
NONPROD application pruning is enabled under the resource ownership policy.
PROD and root Applications do not automatically prune. Database volume retention
is explicit. Every Service and platform resource has one declarative owner;
application namespace resources belong to their environment definitions and
platform resources to their platform definitions.

STAGE image updates are direct automated commits after successful main CI.
DEV and PROD promotion use manual, reviewed GitOps changes. Git rollback is an
explicit operator action; Argo CD reconciles the selected rollback state.

## Jenkins and delivery

One persistent Jenkins controller runs in NONPROD with zero executors.
Application builds run on the separate `host-ci` agent alongside an isolated,
privileged Docker-in-Docker daemon. The trusted `registry-publisher` agent has
its own workspace and executes pinned publisher helpers. Application build code
does not receive registry-publishing or infrastructure-writing credentials.
The privileged build daemon's isolation does not provide a separate physical
security boundary from its K3s node.

The controller preserves operator identities, credential scopes and retained
build history. Its startup configuration restores normal execution of the
approved jobs and triggers. Agent images, plugins and tools are pinned;
workspaces, Docker cache and controller state have separate storage lifecycles.

### Build and promotion policy

Main SCM polling runs approximately every two minutes. Automation is limited
to the agreed main pipeline and explicit promotion entrypoints; nightly
schedules and recurring multibranch indexing are disabled.

```mermaid
flowchart LR
  Main[Application main commit] --> CI[CI / tests / image build]
  CI --> Publisher[Trusted immutable-image publisher]
  Publisher --> GitOps[Direct STAGE digest commit to infrastructure main]
  GitOps --> Argo[Argo CD deploys STAGE]
  Argo --> Acceptance[Automatic STAGE acceptance]
  Acceptance --> ProdRequest[Manual release-tag PROD promotion]
```

- **DEV:** an operator requests deployment of a selected application branch.
  DEV is independent of STAGE and is not a mandatory promotion step.
- **STAGE:** a merge into application main runs CI for the resulting main
  commit. Successful CI exports images that passed its configured gates to the
  trusted publisher,
  which publishes immutable frontend/backend images and directly commits the
  pair to infrastructure main. Argo CD deploys that state without a STAGE PR
  or human approval.
- **PROD:** an operator selects a release tag and the exact image digest pair
  accepted in STAGE. A reviewed GitOps change promotes that pair without
  rebuilding either image.

Publication, STAGE promotion and acceptance are serialized through one publisher
lock. The writer rechecks exact application main immediately before each
infrastructure push. Superseded builds are skipped, including when a newer
commit fails CI. A failed newer build leaves the deployed STAGE version intact.
Infrastructure updates preserve unrelated concurrent changes. Automated writes
are limited to the intended STAGE image, promotion and acceptance files.

### Automatic STAGE acceptance

A separate observer checks Argo CD Synced/Healthy, the ready running
frontend/backend digest pair and a STAGE HTTPS smoke request. Acceptance records
bind the application SHA, both digests and infrastructure/Argo revisions.
The observer has only the read access needed for observation; the trusted
writer records the acceptance result.

PROD promotion requires a successful automatic acceptance record for the exact
pair and release source. Failed or superseded acceptance cannot qualify a
release. Rollback remains manual.

## Monitoring and operational configuration

Each cluster has independent Prometheus, Alertmanager and Grafana configuration,
credentials and metrics storage. Prometheus Operator, kube-state-metrics and
Node Exporter provide cluster monitoring. Argo CD, Traefik and application
monitoring use internal endpoints, provisioned dashboards and alert rules.
Exporter endpoints are not administrative browser services.

Resource limits, retention, dashboard provisioning and storage budgets are
explicit per-cluster configuration. Alert delivery has configured destinations
and routing; notification channels, log collection and external uptime checks
are selected within the observability design and resource budget.

## Secrets and repository boundaries

Operators create Kubernetes Secrets with Ansible, the reviewed provisioning
helpers or a deliberate manual procedure using private inputs under `recovery/`.
Live inputs are Git-ignored and included in the protected offsite recovery kit.
No live Secret payloads, plaintext or encrypted, belong in Git. Tracked files
contain only visibly fake examples, Secret references and provisioning logic.

Application, database, registry, GitHub App and Cloudflare credentials have
distinct purposes and scopes. Public manifests and logs contain no live
credential values. Rebuilding a cluster restores private inputs and provisions
Secrets before the workloads that consume them.

| Repository or path | Responsibility |
| --- | --- |
| Application repository | Application code, tests, image builds, release tags and Jenkins pipeline/publisher source |
| Infrastructure repository | Infrastructure provisioning, Kubernetes/platform resources, image references, GitOps, Jenkins deployment/bootstrap and recovery procedures |
| `kubernetes/apps/liora/` | Shared application base, environment overlays and promotion/acceptance records |
| `kubernetes/gitops/argocd/` | Independent roots, Applications and AppProjects for both clusters |
| `kubernetes/platform/nonprod/` | NONPROD administration, monitoring and Jenkins platform |
| `kubernetes/platform/prod/` | PROD administration and monitoring |
| `recovery/` | Tracked examples/helpers and ignored private recovery inputs |
| `runbooks/` | Installation, operation and disaster recovery procedures |
| `docs/testreports/` | Implementation plan, migration history and execution reports |
| `.local-work/` | Ignored operator tools, generated output and private working data |

Application and infrastructure Git histories remain independent. Pipeline checks
of application ancestry and release tags use application history; deployment
writes use infrastructure history. Live credentials, private keys, Terraform
state and operator data are never committed.

## Availability boundaries

Two clusters provide separate control planes and environment ownership on one
physical Proxmox host. The HAProxy edge and Tailscale router each have their own
VM. Common power, host and storage remain shared failure domains. HAProxy
VM 240 is a single point of failure for public application access.

The project shares one public IPv4 address between host/Proxmox administration
and application DNAT to HAProxy. Keeping this working edge and its node pools
is an accepted limitation; a separate ingress-VIP migration is not planned.
Private cluster VIPs and public IP allocation are separate network decisions.

API/VIP elections, application replicas, database replication and persistent
storage recovery solve different availability problems. None substitutes for
host-independent backups or a complete recovery procedure. Physical-host
redundancy is outside this topology.


## Optional longer-term improvements

These are optional reviews, not prerequisites for the current platform:

- For increased scale or availability requirements, reassess the single edge
  failure domain, available public IP addresses and a redundant public ingress
  design. An additional public IP may form part of that design; this is not a
  required change to the current topology.
- Reassess PROD Adminer in approximately one to two years, once the system has
  demonstrated stable operation and direct interventions have become exceptional.
  Remove it only if a practical alternative operational path is available.
