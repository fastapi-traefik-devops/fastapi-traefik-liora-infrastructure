# Liora — Local disaster recovery test report

Generated 2026-10-24T10:19:25+02:00.

## Outcome

Completed real sequential local tests with **25 captured screenshots (24 unique images)**, saved command output, API responses and per-test records. Full R2 database recovery and recovered Liora application verification remain **BLOCKED**. No full Proxmox recovery was attempted or claimed.

The three originally running local Jenkins containers were stopped at the user’s request. Desktop/browser documents were left open. The lab and component workloads are stopped at completion; original containers and volumes remain available.

[Evidence index](astra-review/INDEX.md) · [Presentation selections](DR_PRESENTATION_FINAL_EVIDENCE.md)

| Test | Actual outcome | Evidence and meaning |
|---|---|---|
| 01-kubernetes | **PASS** | Local API, Ready node, pod scheduling, PVC survived replacement and later node stop/start. [Detailed record](evidence/real/2026-10-24-local/01-kubernetes/RESULT.md) |
| 02-cloudnativepg-r2 | **PARTIAL / RESTORE BLOCKED** | Exact CNPG/Barman/cert-manager installed; no protected backup/WAL or read-only R2 credentials. [Detailed record](evidence/real/2026-10-24-local/02-cloudnativepg-r2/RESULT.md) |
| 03-application | **BLOCKED** | Pinned backend/frontend anonymous pulls returned GHCR 401; no recovered database. [Detailed record](evidence/real/2026-10-24-local/03-application/RESULT.md) |
| 04-argocd | **PASS within local scope** | Held definitions restored; actual ConfigMap Git sync Succeeded, Synced and Healthy. [Detailed record](evidence/real/2026-10-24-local/04-argocd/RESULT.md) |
| 05-monitoring | **PASS within local scope** | 30 original rules loaded, dashboards imported, local metrics displayed, synthetic alert fired/resolved. [Detailed record](evidence/real/2026-10-24-local/05-monitoring/RESULT.md) |
| 06-jenkins | **PASS for synthetic state** | Existing helper staged real synthetic controller archive; restored keys decrypt marker and job remains disabled. [Detailed record](evidence/real/2026-10-24-local/06-jenkins/RESULT.md) |
| 07-rollback | **PASS for synthetic workloads/data** | Actual workload rollback and PostgreSQL logical table checkpoint restored and asserted. [Detailed record](evidence/real/2026-10-24-local/07-rollback/RESULT.md) |
| 08-cleanup | **PASS** | No running containers; original containers/volumes retained; lab stopped, one owned container removed. [Detailed record](evidence/real/2026-10-24-local/08-cleanup/RESULT.md) |

## Resource and isolation preflight

8 logical CPUs, 7.6 GiB RAM, initially about 2.1–2.3 GiB available, 3.9 GiB swap used and 205 GiB free disk. Docker, kind, k3d, kubectl and libvirt were present. Initial sandbox access to Docker/libvirt/snap was denied; approved host-level execution resolved runtime access without changing host permissions or services.

Existing VMs lemp-server/win10 and k3d labs flagship-platform/gitlab-gitops were already stopped. Only the identified running containers infra-agent-1, infra-jenkins-1 and infra-docker-1 were stopped. No broad cleanup was used.

New single-node cluster: **liora-dr-20261024**, K3s **1.35.5+k3s1** from a cached image. This differs from repository K3s 1.36.5 and does not establish exact source-platform compatibility. Node UID anchor (kube-system): `aa85f393-9b41-42a5-af6a-7fadfc783683`. API bind `127.0.0.1:16443`. All Kubernetes mutations targeted the exact lab node through docker exec; a separate private kubeconfig was used for Argo UI forwarding. The default kube context remained k3d-gitlab-gitops.

Initial node cap 1536 MiB; temporary Argo phase cap 2048 MiB. Database/backup workloads were hibernated or scaled down before Argo; Kubernetes was stopped before monitoring; Prometheus/Grafana stopped before Alertmanager; Alertmanager stopped before Jenkins; Jenkins stopped before rollback. Final node/PVCs are retained but stopped. Dedicated monitoring/Jenkins Docker network had no outbound gateway.

## Measurements

| Measurement | Observed | Boundary |
|---|---|---|
| Successful k3d creation | About 9s in create-retry.log | Ready/storage checks followed; not platform RTO |
| Argo core install / held definitions | About 85s | 09:58:39–10:00:04 local, excludes later Git-transport troubleshooting |
| Successful Argo ConfigMap sync | Under 1s at 1s log resolution | Both timestamps 08:01:14 UTC; not full application recovery |
| Synthetic Jenkins source-ready → restored-ready | About 71.5s | Includes observation/shutdown/staging; not restore-only timing |
| Kubernetes workload rollback | 2.204s | Includes HTTP and PVC marker verification |
| PostgreSQL logical table rollback | 0.602s | Restore plus SELECT/assertion; not WAL/PITR |
| Successful combined rollback exercise | 36.926s | Excludes the failed Alpine attempt and cluster restart |
| Final host resource snapshot | 3.6 GiB available RAM; 2.7 GiB swap; 200 GiB disk available | Cached images, stopped lab and private synthetic state retained |

Component resource snapshots: Kubernetes storage phase 565.8 MiB/1.5 GiB; backup dependencies 961.6 MiB/1.5 GiB; Argo 1.368 GiB/2 GiB; Prometheus 107.2 MiB/384 MiB; Grafana 259 MiB/512 MiB; restored Jenkins 206.4 MiB/640 MiB; final lab before shutdown 762.9 MiB/2 GiB. These are snapshots, not peak-use measurements.

## Per-test execution records

### 01-kubernetes

Executed 24 October 2026, approximately 09:49–09:51 Europe/Tirane.
One K3s 1.35.5 server, capped at 1536 MiB; 565.8 MiB measured after test.
Cluster kube-system UID: aa85f393-9b41-42a5-af6a-7fadfc783683.
API published only on 127.0.0.1:16443. Existing host kubeconfig was not changed.

Node Ready, API access, pod scheduling and Bound 64Mi local-path PVC verified.
Marker `liora-dr-20261024` survived a real deployment rollout to a new pod.
The storage workload was scaled to zero immediately afterward; PVC retained for rollback.
Read [verification-retry.log](evidence/real/2026-10-24-local/01-kubernetes/verification-retry.log) for actual commands, events and exit code 0.

Failures retained: first k3d creation with --no-image-volume automatically rolled back;
first image import reported a missing multi-platform digest; stdin forwarding was corrected.
Kubelet then successfully pulled Alpine directly, as shown in events.

Limitations: this tests one disposable local node and pod replacement, not node/disk loss,
HA, Proxmox restoration, or original platform Kubernetes 1.36.5 compatibility.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 02-cloudnativepg-r2

24 October 2026, approximately 09:51–09:54 Europe/Tirane.
CNPG 1.30.1, cert-manager 1.21.2 and Barman Cloud Plugin 0.15.1 installed
from repository manifests with unchanged pinned OCI digests into the local lab.
See operator-install.log and dependencies.log for real rollouts and certificates.

No protected physical backup copy, WAL set, or independently verified read-only
R2 identity is available. The user confirmed no such local inputs are held.
The existing report describes a writer/delete identity, unsuitable for this lab.
No R2 credentials were imported, no ObjectStore was created and no original
archive was accessed. Therefore no restored schema/users/data/PITR result exists.

Historical DEV backup IDs in Phase 10.2 are documentary references, not independently
verified available backups today: 20261023T135047 (PITR), 20261023T154448 (full cycle).
The old source-dependent pitr.py was not run because it writes live markers and
queries original Kubernetes environments.

The dependency startup proves installability on this local node, not R2 recovery.
A later application fallback may use a fresh synthetic local database, clearly
separate from any recovered DEV data.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 03-application

The actual pinned DEV frontend/backend images were requested in the isolated
namespace dr-application. Both GHCR pulls returned HTTP 401 Unauthorized.
See events.log. Failed application Deployments were scaled to zero.

No registry credential was available in the lab, and no original Kubernetes
cluster was queried to obtain one. The older cached backend/frontend images are
from August and do not match pinned release digests, so they were not presented
as recovery of the documented release.

A new synthetic CNPG PostgreSQL database was attempted with generated credentials
for a later independent local rollback test. This is initdb, not a restored R2
backup. Migrations/login/authentication/CRUD/application persistence were NOT
verified. No production migrations or application connections occurred.

A first over-broad lab egress policy also blocked CNPG API access. The policy was
narrowed to application pods; database access to its local API was restored.

The fresh PostgreSQL 16.15 cluster reached Ready and was hibernated to release
RAM before Argo CD. Its PVC remains Bound. startup.log says backend/frontend
"successfully rolled out" after they had been scaled to zero; that message does
NOT prove either application ran. events.log records the actual 401 failures.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 04-argocd

Argo CD 3.5.6 restored from the repository's pinned upstream commit.
Core server, repo server, Redis and application controller became Ready.
Dex, notifications and ApplicationSet controllers remained at zero replicas.
Two actual DEV/STAGE Application definitions were adapted to dr-gitops with
skip-reconcile=true, automation disabled and a project permitting only the local API.
They were accepted, but full DEV/STAGE workloads were intentionally not synced.

A separate AppProject allowed only ConfigMaps in dr-gitops from the disposable
local Git server. Actual Argo reconciliation synced recovered-backend-config,
using sanitized data derived from the original backend ConfigMap.
Operation Succeeded, resource Synced, application Healthy, commit
6f94205198d0b93745144059e363673df78a33a6.
Operation timestamp 08:01:14 UTC → 08:01:14 UTC (under one second at recorded
one-second resolution). Total installation started 09:58:39 Europe/Tirane;
core installation/held definitions completed about 10:00:04.
Node measured 1.368 GiB under a temporary 2 GiB cap.

First static-HTTP Git attempt failed with unexpected EOF; retained in sync.log
and 01-applications-ui.jpg. Switching to a lab-bridge read-only Git daemon fixed it.
See sync-retry.log and the actual Argo UI screenshots.
Anonymous UI access was read-only and reachable only through loopback forwarding.
No production cluster credentials or destination were registered.

This proves local controller startup, adapted GitOps object acceptance and a
real ConfigMap sync. It does not prove full application restore, preserved Argo
history/SSO/secrets, or restoration of original controller persistent state.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 05-monitoring

24 October 2026, approximately 10:02–10:08 Europe/Tirane.
Existing cached kube-prometheus-stack 92.2.0 chart was rendered to identify versions.
Prometheus 3.15.0 (cached standard image, same version as chart's distroless tag),
Grafana 13.2.3-distroless (exact chart tag), Alertmanager 0.34.1 (exact chart tag).

Original PrometheusRule groups from NONPROD monitoring and backup-monitoring
were converted directly to native rule files. promtool verified 15 + 15 rules.
The running Prometheus API returned loaded/evaluated rules with healthy state,
and the real self-scrape target was UP. No original Kubernetes exporters or
production targets were scraped; missing-series alerts may fire by design.

Original dashboard JSON imported with datasource UID prometheus. Grafana database
health returned ok and API listed restored dashboards. Original operations panels
show No telemetry because their source exporters are absent. An additional
clearly labeled LOCAL DR dashboard displayed actual up=1 and Prometheus process
memory metrics, never invented or copied production samples.

Prometheus measured 107.2 MiB under 384 MiB cap; Grafana 259 MiB under 512 MiB.
These components were stopped before Alertmanager's separate test (128 MiB cap).
A real synthetic alert was accepted (HTTP 200), displayed under discard receiver,
then resolved (HTTP 200); API returned zero active alerts and UI no alert groups.
All external receivers/Slack credentials were omitted. The Docker network is
internal with no outbound gateway; failed Grafana external plugin lookup is
recorded in logs. Host accessed private bridge IPs because internal-network port
publishing did not become available on localhost.

See six actual product UI screenshots, API JSON, logs, resource-usage.log and
rule-validation.log. Original TSDB/history/PVCs, Kubernetes scrape coverage,
production notification delivery and full operator/chart recovery were not tested.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 06-jenkins

24 October 2026, approximately 10:08–10:11 Europe/Tirane.
Exact repository Jenkins base image 2.585-alpine-jdk21, pinned digest
sha256:e00aee28e0233941e1c952062b2c6f47e44447f8f5a74243dd9ac4e7d7298030.
The full custom controller/plugin image and a current original Jenkins backup
were unavailable; a real disposable controller supplied synthetic local state.

Source controller generated actual encryption files, an admin password hash,
a disabled freestyle job, and an encrypted synthetic marker. Source was stopped
before archiving. The existing, unmodified stage-jenkins-home.py validated and
prepared its 52,299,857-byte archive. It preserved both master.key and
hudson.util.Secret and rewrote controller/job configuration into held state.
A second actual controller booted from the staged archive and successfully
decrypted the retained synthetic marker. No key values or passwords appear
in public evidence. Source archive SHA-256 is in archive-receipt.json.

Source readiness: 08:08:38.498 UTC. Restored readiness: 08:09:49.972 UTC.
This interval includes observation, source shutdown and archive/staging work;
it is not a production Jenkins RTO or a precise restore-only duration.
Both API snapshots prove numExecutors=0, quietingDown=true, job buildable=false,
no builds. Three screenshots show source/restored UI and disabled job status.
The internal Docker network has no outbound gateway, no agent or Docker socket
was mounted, and no pipeline/deployment/publishing operation was executed.

This proves an actual synthetic controller-home restore using the existing
archive transformation, matching encryption material and job preservation.
It does not prove recovery of original jobs, historical builds, original
credentials, plugin configuration/compatibility, GitHub integrations or
production Jenkins state. Empty build history was verified, not invented.
Private source/staged/restored homes and backup archives are retained under
private/, excluded from public evidence and Git.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 07-rollback

Actual run 24 October 2026, 10:13:31 Europe/Tirane, 36.926s total.
Workload HTTP response v1 → v2 → v1 after real kubectl rollout undo.
Measured workload rollback including verification: 2.204s.
The original PVC marker liora-dr-20261024 survived cluster stop/start and both rollouts.

Fresh synthetic CNPG PostgreSQL 16.15 resumed from its retained 2Gi PVC.
pg_dump captured a real custom-format checkpoint of public.dr_checkpoint.
After update/insert, pg_restore --clean --if-exists restored that test table.
Before: 1|checkpoint-v1. Changed: 1|changed-v2 plus 2|after-checkpoint.
After rollback: exactly 1|checkpoint-v1, independently asserted by the runner.
Logical rollback including verification: 0.602s.
Database Ready, original PVC Bound, plpgsql and uuid-ossp extensions verified.

First attempt failed because Alpine lacked httpd. first-failure.log and first-run.log
retain the error/90s rollout timeout. Switching only the disposable HTTP fixture
image to BusyBox 1.37 fixed it. Every executed command and exit code is retained
in rollback.log. Focused log-viewer screenshots are labeled as recorded output.

This is a real Kubernetes workload rollback and a real PostgreSQL logical table
checkpoint restoration, using synthetic local data. The HTTP workload is a
BusyBox fixture, not recovered Liora. This is NOT WAL replay, PITR, an R2 restore,
full database recovery, original data integrity verification or Proxmox DR.

[All commands, logs and screenshots](astra-review/INDEX.md)

### 08-cleanup

24 October 2026, approximately 10:15 Europe/Tirane. See cleanup.log and receipt.json.
Before shutdown the local CNPG database and operator were Ready and both lab PVCs
Bound. Node memory usage was 762.9 MiB under its 2 GiB cap.
The exact owned k3d cluster was stopped. The disposable Git-serving container's
run label was verified before removing only that container. An inspect afterward
returned expected exit code 1. No prune, shared-volume or broad-delete command ran.
The exercise's read-only Git listener was terminated after its final use.

Final docker ps was empty. The three original infra containers still exist,
are stopped by user request, and retain their volume attachments. Both original
VMs and both pre-existing k3d clusters remain stopped. Default kube context
remains k3d-gitlab-gitops. Both original repositories report clean working trees.
Final snapshot: 3.6 GiB available RAM, 2.7 GiB swap used, 200 GiB disk available.

Lab node/PVCs, stopped component containers, cached images and private synthetic
archives are retained for review/repetition; cleanup does not claim zero retained
disk use. The loopback evidence viewer is terminated after the last screenshot.
All evidence and reports remain saved. No production cluster or Proxmox endpoint
was contacted, no R2 identity imported, and no production mutation was issued.
This statement describes this run's command scope; no independent remote audit
or before/after content hash of original volumes was performed.

[All commands, logs and screenshots](astra-review/INDEX.md)

## Historical PITR evidence from the repository

The user asked to reuse existing repository documents/screenshots when a protected backup was unavailable. Historical sources are linked without duplication under [evidence/historical](astra-review/HISTORICAL_REFERENCES.md). Source infrastructure commit `ff154ae7a81858f5dcdf49d0582cb1d1074a6943`; application checkout `7aaf28740b227fee925e23383d6d589a3ea35336`. Both checkouts remained clean.

The [existing Phase 10.2 report](../phases/phase-10/history/r2-backup-pitr-2026-10-23.md) reports these original-environment exercises on **23 October 2026**:

| Environment | Historical backup ID | Historical target UTC | Historical usable-app time |
|---|---|---|---|
| DEV | 20261023T135047 | 13:54:33.341887 | 286.163s |
| STAGE | 20261023T140627 | 14:10:38.064581 | 195.483s |
| PROD | 20261023T142102 | 14:27:18.292025 | 287.029s |

These values are historical documented claims, not independently repeated local results. Their clock begins with working K3s/R2 and excludes infrastructure rebuilding. No original detailed PITR screenshots/private backup set was found in this checkout. Existing Grafana PNGs demonstrate historical monitoring only; NONPROD assurance shows an older backup instrumentation gap, and PROD operations shows one critical alert. Neither establishes successful recovery today. The old simulated DR PNGs were excluded from this real evidence collection.

## Reproduction and remaining inputs

Selected recorded scripts/manifests live in [disaster-recovery-local](astra-review/recorded-scripts). test01.sh, test02.sh, prepare-app.py, prepare-argocd.py, prepare-monitoring.py, stage-real-jenkins.py, test07.py and test08.py preserve the implementation and scoped command patterns. Scripts assume this specifically identified lab and recorded state; read the evidence first. The recorded scripts preserve their original workspace assumptions and are not turnkey runners from this directory. Use astra-review/scripts/verify_local_lab.py for guarded read-only rechecks. test07.py intentionally creates a new synthetic table and is not blindly rerunnable over an existing checkpoint table. prepare-app.py refuses credential regeneration when private credentials already exist.

For a genuine new R2 restore, supply a protected DEV physical backup plus complete required WAL/metadata or an independently verified read-only R2 identity. Original writer/delete credentials must stay out of the restore lab. For recovered-app acceptance, also supply read-only registry access to the exact pinned backend/frontend digests and the required independent recovery inputs. A document or screenshot cannot supply the missing physical data.

Private generated credentials, Jenkins encryption state and synthetic archives remain under disaster-recovery-local/private/ (0700 directory), and kubeconfig is mode 0600. They are excluded from evidence serving, the public archive and Git. This publication contains none of those private files. No credential values were placed in public logs. The loopback evidence viewer was temporary and is stopped at completion. No commit/push was made during the runtime exercise. The later publication audit is documented separately in DR_INDEPENDENT_AUDIT_REPORT.md.

No Proxmox, DEV/STAGE/PROD Kubernetes API, R2 archive, production DNS/certificate, production Jenkins pipeline or external notification destination was mutated or queried during this run. This is a statement of executed command scope, not a remote forensic audit.
