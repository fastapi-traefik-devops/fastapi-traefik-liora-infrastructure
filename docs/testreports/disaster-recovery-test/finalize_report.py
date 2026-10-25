#!/usr/bin/env python3
"""Assemble factual report/index from saved results; does not contact infrastructure."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[2]
E=ROOT/'evidence'


def main():
    local=json.loads((E/'real/local-checks.json').read_text())
    tls=json.loads((E/'real/local-https-results.json').read_text())
    sim=json.loads((E/'simulated/results.json').read_text())
    before=json.loads((E/'real/live-before.json').read_text())
    after=json.loads((E/'real/live-after.json').read_text())
    def comparable(data):
        result=json.loads(json.dumps(data['clusters']))
        for kinds in result.values():
            for rows in kinds.values():
                if not isinstance(rows,list):raise RuntimeError('Incomplete live evidence')
                for row in rows:
                    for k in ['ready','health','sync','phase']:row.pop(k,None)
        return result
    first,last=comparable(before),comparable(after)
    diff=[{'cluster':c,'kind':k} for c in first for k in first[c] if first[c][k]!=last[c][k]]
    comparison={'before_utc':before['timestamp_utc'],'after_utc':after['timestamp_utc'],
                'audited_configuration_and_identity_equal':first==last,'differences':diff,
                'observed_resource_counts':{c:{k:len(v) for k,v in kinds.items()} for c,kinds in first.items()},
                'coverage':'Node UIDs; Deployment/StatefulSet UIDs, replicas, images; PVC UIDs/PV binding; Application UIDs/specs; Ingress UIDs/specs.',
                'limitations':['Not an exhaustive audit. No DNS/firewall/R2/Proxmox/Secret-data/Jenkins-history comparison.',
                               'Read-only GET queries only. No production mutation commands issued.']}
    (E/'real/live-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    provenance={}
    infra=WORKSPACE if (WORKSPACE/'kubernetes').is_dir() else WORKSPACE/'infrastructure'
    application=infra.parent/'application'
    for name,p in [('infrastructure',infra),('application',application)]:
        if not p.is_dir():
            provenance[name]={'revision':None,'status_porcelain':'SOURCE CHECKOUT UNAVAILABLE'}
            continue
        provenance[name]={'revision':subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip(),
                          'status_porcelain':subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True).strip()}
    provenance['remote_infrastructure_revision']=before.get('repo_revision')
    (E/'real/repository-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    now=datetime.now(ZoneInfo('Europe/Tirane')).isoformat()
    comparison_text='No differences found in the compared fields.' if first==last else 'Differences observed; inspect live-comparison.json. Do not attribute them without investigation.'
    report=f'''# Liora disaster recovery test report

Generated: {now} (Europe/Tirane). Evidence timestamps retain UTC.

## Outcome and scope

**Complete infrastructure recovery: BLOCKED. Local software verification: PASS. Synthetic recovery sequence: completed under mocks.**

No separate recovery Proxmox endpoint, independent storage/network or complete off-site recovery kit was available to this execution. Real recovery tests were gated at the read-only preflight; none was attempted against the existing environments. The available fallback was used: synthetic recovery simulations, actual offline repository-helper tests, and a disposable loopback HTTPS/SQLite fixture.

**No Proxmox host, VM, K3s cluster, CNPG database, FastAPI/React deployment, ArgoCD, Jenkins, Grafana, HAProxy or R2 archive was recovered in this run.** No real infrastructure test below is marked PASS because a mock passed.

All example screenshots carry **SIMULATED — NOT A REAL TEST**. They are purpose-built mock evidence panels, not captures of production product interfaces. Actual local check evidence is kept separately under `evidence/real/`; that directory also contains read-only live metadata, not real recovery screenshots.

## Read-only safety preflight

- Workstation: 8 logical CPUs, approximately 7.6 GiB total RAM and 2.4–2.5 GiB available during preflight, approximately 204 GiB free disk. No `/dev/kvm` exposed.
- Existing Docker API access was denied; libvirt could not create its required runtime directory under the current permissions. No service, permission, runtime or virtualization setting was changed to bypass this.
- No independently identified recovery host, lab API identity or reserved capacity was supplied. Installing Proxmox or creating VMs on this workstation would not be justified by these findings.
- Local kubeconfig points to an unrelated existing `k3d-gitlab-gitops` context. It was inspected and never used for mutation or as a recovery lab.
- Protected recovery-input **presence only** was checked on the management host. Values were not retrieved, validated or copied. Presence on a host in the original failure domain is not independent recovery availability.
- No R2 credentials were loaded and no R2 objects were read, downloaded, copied, written or deleted. Required immutable copied physical backups and a restricted restore identity remain unavailable/unverified.
- Existing live configuration was sampled before and after via explicit kubeconfigs and read-only `kubectl get` calls over the already trusted SSH connection.

Evidence: [local preflight](docs/testreports/disaster-recovery-test/evidence/real/local-preflight.json), [before](docs/testreports/disaster-recovery-test/evidence/real/live-before.json), [after](docs/testreports/disaster-recovery-test/evidence/real/live-after.json), [comparison](docs/testreports/disaster-recovery-test/evidence/real/live-comparison.json).

## Recovery test matrix

Status refers to the **real named recovery test**, not the simulation. “Completed” in the simulation column means assertions passed using the stated stand-ins. `NOT EXECUTED` states why there is no real measurement/action; BLOCKED is the overall test status.

| Test | Real result | Simulation result | Evidence | Status |
|---|---|---|---|---|
| 1. Complete Proxmox host failure | NOT EXECUTED: no independent lab; original host deliberately left running | Synthetic source directory removed after independent fixture bundle was copied; sequence continued without it | [Mock host-loss panel](docs/testreports/disaster-recovery-test/evidence/simulated/01-proxmox.png), steps 1–2 | BLOCKED |
| 2. Proxmox networking and VM rebuild | No separate hypervisor, lab credentials, storage or network | Nine JSON VM records and a documentation-only lab subnet reconstructed | [Proxmox panel](docs/testreports/disaster-recovery-test/evidence/simulated/01-proxmox.png), step 2 | BLOCKED |
| 3. K3s using Terraform and Ansible | No disposable hypervisor/cluster target; neither tool applied | Two mock clusters with three Ready node records each; not a Terraform provider or Ansible execution | [Nodes panel](docs/testreports/disaster-recovery-test/evidence/simulated/02-kubernetes.png), step 3 | BLOCKED |
| 4. Kubernetes configuration and Secrets | No independent cluster and no verified complete off-site Secret inventory | Synthetic config/Secret file restored from fixture bundle, permission 0600 checked | [Nodes panel](docs/testreports/disaster-recovery-test/evidence/simulated/02-kubernetes.png), step 4 | BLOCKED |
| 5. CNPG restore from copied R2 backups | No copied physical archive or read-only R2 identity; no CNPG target | Real local SQLite fixture copied/opened; independent of deleted synthetic source | [Database panel](docs/testreports/disaster-recovery-test/evidence/simulated/03-database.png), step 5 | BLOCKED |
| 6. PostgreSQL PITR | No PostgreSQL/Barman recovery environment or copied WAL | SQL event-list replay into SQLite; included marker retained, later marker excluded. Not PostgreSQL WAL replay | [Database panel](docs/testreports/disaster-recovery-test/evidence/simulated/03-database.png), step 6 | BLOCKED |
| 7. FastAPI and React restoration | No isolated deployment target or independently supplied deployable image/Secret set | In-process adapter exercised recovered SQLite fixture; no FastAPI/React process | [Application panel](docs/testreports/disaster-recovery-test/evidence/simulated/04-application.png), step 7 | BLOCKED |
| 8. ArgoCD restoration/GitOps | No isolated ArgoCD controller; live Applications inspected only | Mock drift comparison/reconciliation with automation disabled; real source policies inspected offline | [GitOps panel](docs/testreports/disaster-recovery-test/evidence/simulated/05-argocd.png), step 8 | BLOCKED |
| 9. Jenkins configuration/jobs/history | No current independent Jenkins home/key archive and target controller | Held synthetic job/build records restored. Separately, 12 actual repository archive fixture tests passed | [Jenkins panel](docs/testreports/disaster-recovery-test/evidence/simulated/06-jenkins.png), [actual fixture log](docs/testreports/disaster-recovery-test/evidence/real/jenkins-fixture-tests.log) | BLOCKED |
| 10. Monitoring and alerting restoration | No isolated Prometheus/Grafana/Alertmanager deployment; historical PVC backups unverified | Mock targets and local firing/resolution transitions with external notifications disabled | [Monitoring panel](docs/testreports/disaster-recovery-test/evidence/simulated/07-grafana.png), step 10 | BLOCKED |
| 11. HAProxy and isolated HTTPS | HAProxy/Traefik not restored. Actual independent loopback TLS/Host checks passed with a Python fixture | Mock routing/SNI metadata checked separately; no public DNS or ACME operations | [Routing example](docs/testreports/disaster-recovery-test/evidence/simulated/04-application.png), [real TLS fixture results](docs/testreports/disaster-recovery-test/evidence/real/local-https-results.json) | BLOCKED |
| 12. Recovered application auth/API/CRUD | Recovered FastAPI/React not available. Python/SQLite HTTPS fixture accepted/rejected synthetic credentials and performed CRUD | Mock app adapter auth, integrity and CRUD assertions completed | [Application panel](docs/testreports/disaster-recovery-test/evidence/simulated/04-application.png), [real fixture results](docs/testreports/disaster-recovery-test/evidence/real/local-https-results.json) | BLOCKED |
| 13. Actual platform RPO/RTO | NOT MEASURABLE: no real outage/recovery; no independent current commit/WAL baseline | Synthetic time 35 minus replayed event time 20 = 15 fixture units; explicitly not actual RPO | [Completion panel](docs/testreports/disaster-recovery-test/evidence/simulated/08-completion.png), step 13 | BLOCKED |
| 14. Full lab rollback | No real infrastructure lab exists. Local filesystem checkpoint and SQLite byte-level rollback genuinely passed | Mock lab reset to recorded initial checkpoint | [Rollback panel](docs/testreports/disaster-recovery-test/evidence/simulated/09-rollback.png), [TLS rollback](docs/testreports/disaster-recovery-test/evidence/real/local-https-results.json) | BLOCKED |
| 15. Infrastructure cleanup verification | No infrastructure test resources created, so real teardown was NOT EXECUTED. Local fixture cleanup verified | Owned fixture removal, run-ID checks and source-copy hash preservation completed | [Cleanup panel](docs/testreports/disaster-recovery-test/evidence/simulated/10-cleanup.png), step 15 | BLOCKED |

All 15 detailed simulation records: [results.json](docs/testreports/disaster-recovery-test/evidence/simulated/results.json). Script: [run_local_tests.py](docs/testreports/disaster-recovery-test/run_local_tests.py).

## What genuinely passed locally

**30 local test/check cases plus five static GitOps assertions passed.** These are actual software checks, not evidence of whole-system recovery:

1. **12 existing Jenkins archive fixture tests**, run on byte-identical copies of the inspected repository helper in a disposable directory. Tests cover archive integrity, unsafe paths/links/duplicates, unknown job types, absent encryption inputs, private input handling, held job configuration, build/key preservation and redacted errors. No Jenkins runtime or real credential decryption occurred. Source hash and copied-helper hash match in [local-checks.json](docs/testreports/disaster-recovery-test/evidence/real/local-checks.json).
2. **Five new local guard tests:** reject live/unknown endpoints; reject corrupted bundle manifests; refuse unowned cleanup or wrong run IDs; refuse symlink cleanup; deny networking in the mock adapter.
3. **13 actual loopback fixture checks:** TLS certificate/hostname validation; wrong HTTP Host and TLS hostname rejection; absent/invalid fixture credential rejection; create/read/update/delete over HTTPS backed by SQLite; integrity; server/thread/socket shutdown; exact checkpoint rollback; removal of fixture directory and generated TLS private key. This was Python HTTPServer, not HAProxy or FastAPI. Certificate trust was local and custom, not public CA trust.
4. **Five actual source assertions:** three child Application local destinations/pruning/self-healing policies and two root non-pruning policies. These inspect repository YAML only and do not prove runtime synchronization.

Logs and actual result screenshot: [guard tests](docs/testreports/disaster-recovery-test/evidence/real/local-guard-tests.log), [Jenkins tests](docs/testreports/disaster-recovery-test/evidence/real/jenkins-fixture-tests.log), [TLS results](docs/testreports/disaster-recovery-test/evidence/real/local-https-results.json), [local-results screenshot](docs/testreports/disaster-recovery-test/evidence/real/actual-local-checks.png).

## What failed, what was simulated, and what was not executed

- No executed local functional test failed in the final run.
- Runtime availability checks failed: Docker socket access denied and libvirt runtime-path creation unavailable. These are blockers, not failed infrastructure restores.
- The first local Chrome screenshot attempt failed in the restricted sandbox. The approved process retry succeeded. A caption substitution bug was corrected after visual inspection, and all screenshots were regenerated. [Attempt history](docs/testreports/disaster-recovery-test/evidence/real/attempt-history.json)
- Fifteen infrastructure recovery scenarios were simulated with JSON adapters, synthetic secrets, copied SQLite state and SQL event replay. No real product UI/log/backup result was fabricated.
- No real Proxmox failure, VM rebuild, K3s install, copied-R2 restore, PostgreSQL PITR, application deployment, ArgoCD sync, Jenkins startup, monitoring deployment or HAProxy recovery was executed.

## Timings and RPO/RTO

| Measurement | Actual observation | Interpretation |
|---|---:|---|
| Local synthetic 15-step harness | {sim['duration_local_harness_seconds']} seconds | Real elapsed code time using mocks; **not infrastructure RTO** |
| Local loopback TLS/SQLite exercise | {tls['duration_local_seconds']} seconds | Includes fixture creation/checks/shutdown/rollback/cleanup; **not application recovery RTO** |
| Full host/VM/K3s/platform RTO | UNKNOWN / not measured | Requires an independently provisioned lab and start/end criteria |
| Current recoverable database point / achieved RPO | UNKNOWN / not measured | No R2/WAL reads or independent acknowledged-commit comparison performed |
| Synthetic replay gap | 15 fixture clock units | Invented input clock for assertions; **not seconds and not a real RPO measurement** |

Prior PITR results from 23 October remain historical evidence only. They were not rerun or counted as PASS here; their timing excludes rebuilding infrastructure. [Recorded PITR scope](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure/blob/8ff119f37667329294010492ac5826ab6b2a3fce/docs/testreports/PHASE10_2_REPORT.md)

## Isolation, rollback and cleanup confirmation

- Synthetic adapters used no network. Source removal affected only a freshly created fixture directory. The mock checkpoint/ownership inventory was recorded before mock lab changes.
- The actual HTTPS fixture bound **127.0.0.1 only**, used an OS-assigned ephemeral port and generated fixture certificates. No production identity, key, data, DNS or certificate was used. The listener was closed, thread joined and owned temporary directory removed.
- Repository fixture tests operated on copies. Both existing local repositories remain clean at the recorded revisions; no commit, push, merge or PR was created. [Repository provenance](docs/testreports/disaster-recovery-test/evidence/real/repository-provenance.json)
- Mock rollback hash manifest equals the checkpoint manifest. Actual SQLite rollback restores the original database file bytes. Cleanup guards rejected unowned and mismatched targets.
- No real VMs, containers, clusters, namespaces, volumes or backup objects were created, so none required cleanup. Reports, screenshots, source files and logs are intentionally retained as authorized deliverables.
- Live snapshots: {comparison['before_utc']} → {comparison['after_utc']}. **{comparison_text}** Comparison covers six node identities; 49 Deployments; six StatefulSets; 13 PVCs; five Applications; and three Ingresses, using the fields specified in the comparison JSON.
- This is a bounded confirmation, not an exhaustive production audit. It does not prove unchanged Proxmox storage, firewall/DNS, R2 objects, Secret values or Jenkins build history. No mutation calls to those systems were issued. Existing controllers remained active.
- Pre-existing STAGE Application remained Synced/Progressing in read-only observations; other application/root health was Healthy. This exercise neither repaired nor modified STAGE.

## Missing recovery requirements and production-readiness recommendations

1. Supply an independently identified lab host, storage, networks and lab-only API credentials. Avoid additional workloads on the memory-constrained existing clusters.
2. Verify an off-site encrypted recovery kit with separately available decryption access: application/platform Secrets, signing keys, registry readers, Jenkins complete consistent home plus matching encryption files, software versions and deployable image inventory.
3. Locate and verify off-site Terraform state and choose fresh-lab state separation. Off-site etcd snapshots and matching K3s tokens remain UNKNOWN; decide explicitly whether to test etcd restoration or fresh declarative reconstruction.
4. Supply immutable copies of selected R2 physical backups plus all required WAL and archive metadata, or a separately audited read-only restore identity. Original writer/delete credentials must not enter the lab.
5. Implement/review a source-independent CNPG recovery procedure consuming the independent bundle. Existing `pitr.py` reads live Secrets, ConfigMaps, Deployments, CNPG/Backup objects and source SQL, and creates live markers. It was not reused.
6. Define exact rollback ownership, snapshots and cleanup approval boundaries for real resources. Never attach production Terraform state or import live tracking metadata.
7. Decide whether restoring monitoring history, ArgoCD identities/history and the currently active Jenkins state is mandatory; Git manifests alone do not restore these.
8. Test actual reconstructed FastAPI/React and HAProxy privately with lab-only name resolution and reviewed certificates, block notifications/publication, and keep Jenkins/Argo automation held until isolation is accepted.
9. Measure whole-platform RTO from independent bootstrap access through usable application; separately measure DB restore time and RPO against an independently recorded data/commit baseline.

Sources: [DR navigator](infrastructure/01-Disaster_recovery.md), [recovery inputs](infrastructure/runbooks/10-prepare-recovery-inputs.md), [K3s boundary](infrastructure/infrastructure/k3s-cluster/ansible/README.md), [VM sizing](infrastructure/infrastructure/k3s-cluster/terraform/variables.tf), [Jenkins restore evidence](infrastructure/docs/testreports/PHASE9_STATE_RESTORE.md), [monitoring persistence](infrastructure/kubernetes/platform/nonprod/monitoring/README.md), [edge state](infrastructure/edge/haproxy/README.md), [application initialization](application/backend/scripts/prestart.sh), [source-dependent PITR helper](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-infrastructure/blob/8ff119f37667329294010492ac5826ab6b2a3fce/scripts/backups/pitr.py).

## Final recommendation

**CONDITIONAL GO for future isolated real recovery after the missing prerequisites are supplied and reviewed. Full production disaster-recovery readiness remains unproven.**

This run demonstrates local archive-handling checks, fixture recovery logic, real local TLS/CRUD, rollback and guarded cleanup. It does not replace a separate-host recovery exercise. Stop here; no production preparation or mutation is part of these deliverables.

Complete artifact list: [evidence index](docs/testreports/disaster-recovery-test/evidence/INDEX.md). Integrity inventory: [SHA256SUMS](docs/testreports/disaster-recovery-test/evidence/SHA256SUMS).
'''
    if infra==WORKSPACE:
        report=report.replace('](infrastructure/', '](')
        revision=provenance['application'].get('revision') or '7aaf28740b227fee925e23383d6d589a3ea35336'
        report=report.replace('](application/backend/scripts/prestart.sh)',
            '](https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application/blob/'+revision+'/backend/scripts/prestart.sh)')
    report=report.replace('](docs/testreports/disaster-recovery-test/', '](disaster-recovery-test/')
    report=report.replace('](01-Disaster_recovery.md)', '](../../01-Disaster_recovery.md)')
    for prefix in ('runbooks/', 'infrastructure/', 'kubernetes/', 'edge/'):
        report=report.replace(']('+prefix, '](../../'+prefix)
    report=report.replace('](docs/testreports/PHASE9_STATE_RESTORE.md)', '](PHASE9_STATE_RESTORE.md)')
    (ROOT.parent/'DISASTER_RECOVERY_TEST_REPORT.md').write_text(report)
    real_files=sorted(p for p in (E/'real').rglob('*') if p.is_file())
    sim_files=sorted(p for p in (E/'simulated').rglob('*') if p.is_file())
    index=['# Disaster recovery evidence index','',
           '**No real infrastructure recovery was executed.** Real evidence below is local software verification or read-only observation. Mock illustrations carry SIMULATED — NOT A REAL TEST.','',
           '[Complete report](../../DISASTER_RECOVERY_TEST_REPORT.md)','',
           '## Actual local checks and read-only observations','']
    index.extend('- ['+str(p.relative_to(E))+']('+str(p.relative_to(E))+')' for p in real_files)
    index+=['','## Simulated evidence and labeled example screenshots','']
    index.extend('- ['+str(p.relative_to(E))+']('+str(p.relative_to(E))+')' for p in sim_files)
    index+=['','## Reproducibility and safety','',
            'The Python sources under `docs/testreports/disaster-recovery-test/` are retained. Existing repositories were not edited. No dependencies were installed.',
            'The mock runner uses only disposable fixtures and explicitly rejects live endpoints. The HTTPS fixture uses a disposable loopback listener.',
            'The capture script performs read-only live metadata queries and requires the existing trusted SSH access. It is not necessary to rerun it to read these results.',
            'SHA256SUMS paths are relative to the infrastructure repository root. The manifest excludes itself.','']
    (E/'INDEX.md').write_text('\n'.join(index))
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
    files.append(ROOT.parent/'DISASTER_RECOVERY_TEST_REPORT.md')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(WORKSPACE))+'\n' for p in files)
    (E/'SHA256SUMS').write_text(manifest)
    print(json.dumps({'report':str(ROOT.parent/'DISASTER_RECOVERY_TEST_REPORT.md'),'indexed_artifacts':len(real_files)+len(sim_files),
                      'checksummed_files':len(files),'live_fields_unchanged':first==last,'local_repositories_clean':all(not provenance[n]['status_porcelain'] for n in ['application','infrastructure'])}))


if __name__=='__main__':main()
