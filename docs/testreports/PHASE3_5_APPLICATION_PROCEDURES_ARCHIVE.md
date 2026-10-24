# Historical procedure record — 13-deploy-application-manifests

Archived on 2026-10-24 before the operational-manual rewrite. This preserves
one-time decisions, commands, observations and original limitations. Statements
about current status describe their original checkpoint. Do not use this record
as the installation or incident-response entrypoint. Operator scripts remain
in their original locations.

Current procedure: [13-deploy-application-manifests.md](../../runbooks/13-deploy-application-manifests.md).

---

# Deploy and verify the application manifests

**Where:** Management VM 200, from the reviewed infrastructure checkout.

**Run order:** Complete one environment at a time: DEV → STAGE → PROD. Stop at
each acceptance gate. Use the explicit kubeconfig selected in step 1 for every
cluster command.

**Status:** DEV, STAGE and PROD are deployed on their assigned K3s clusters.
Private health, browser login, item persistence and mutual database/token
isolation passed; see the [Phase 3 report](PHASE3_REPORT.md),
[Phase 4 report](PHASE4_REPORT.md), and
[Phase 5 report](PHASE5_REPORT.md). PROD has two Ready backend
and two Ready frontend replicas using the approved image pair `sha-c375967...`.
All three synthetic acceptance markers were removed after isolation checks.

> [!NOTE]
> Run only the steps belonging to the currently authorized phase. Public
> routing, trusted TLS and Argo CD use their separate procedures. Verified
> results are in the Phase 6/7 reports; repeat their gates during fresh recovery.
> The verified migration is integrated into the original checkout on `main`.

## Before you start

### Scope and environment map

Use the pinned CloudNativePG PostgreSQL 16 database, existing Adminer 4.8.1,
and prestart migration Job. [Runbook 18](../../runbooks/18-cloudnative-pg.md) covers operator
installation, bootstrap credentials, fresh database replacement and retirement
of the old database Deployment/PVC. Never repeat that destructive cutover as
a routine application deployment. This procedure does not install Argo CD, monitoring, CloudNativePG, edge
routing, DNS, or certificate automation. Preserve each environment's data.

| Environment | Kubeconfig | Namespace | Configured origin |
| --- | --- | --- | --- |
| DEV | `$HOME/.kube/config-dev-stage` | app-dev | `https://dev.liora.aprt.info` |
| STAGE | `$HOME/.kube/config-dev-stage` | app-stage | `https://stage.liora.aprt.info` |
| PROD | `$HOME/.kube/config-prod` | app-prod | `https://liora.aprt.info` |

> [!NOTE]
> DEV originally kept the source's HTTP ingress and `ENVIRONMENT: staging`.
> Phase 7 changes its origin/CORS and ingress to HTTPS while retaining that
> environment mode. All three environments now reference namespace-local app-tls.
> STAGE/PROD retain HTTPS settings and reference a namespace-local `app-tls`
> Secret. Setting these hostnames does not configure DNS, certificates, or
> public access. A trusted HTTPS check needs a matching certificate and
> private ingress path; otherwise record it as pending. API VIPs are not
> ingress backends; HAProxy uses the Traefik ServiceLB node pools.

Require `kubectl`, Python 3 with PyYAML (`python3 -c 'import yaml'`), access to
both explicit kubeconfigs, and the reviewed Git revision. Each Python block
below also links to a standalone script. Use either the inline block or its
script file; both use the environment variables exported in step 1. You can
copy a script to VM 200 and run it with `python3 /path/to/script.py`, or run
the repository copy using the command beside its link.

The default kubeconfig points to the separate kind reference cluster; never
rely on it for K3s.

Recovery inputs reside in the original checkout:

- `$HOME/fastapi-traefik-liora-infrastructure/recovery/recovery.yaml`:
  `application_credentials.<environment>` holds `first_superuser`, namespace,
  `backend-secrets`, and `db-secrets`. The initial account is
  `admin007@liora.aprt.info` in each separate database.
- `$HOME/fastapi-traefik-liora-infrastructure/recovery/.env`:
  `GHCR_REGISTRY`, `GHCR_USERNAME`, and `GHCR_TOKEN` supply registry read access.

- [ ] Confirm `kubectl`, Python 3, and PyYAML are available:

   ```sh
   python3 -c 'import yaml'
   ```

- [ ] Validate the recovery inputs before deployment:

   ```sh
   RECOVERY_DIR="$HOME/fastapi-traefik-liora-infrastructure/recovery" bash recovery/check_credentials.sh --all --offline
   ```

Install the checker dependencies and review its field and exit-status contract
in the [recovery schema](../../recovery/README.md). Warnings preserve unknown
fields; add `--strict-warnings` when they must fail a gate.

- [ ] Confirm both recovery files are ignored, mode `0600`, and included in
      the operator's external recovery archive.

> [!IMPORTANT]
> Do not print values, use shell tracing, put credentials in command
> arguments, or commit generated Secret manifests. Provision Secrets with the
> reviewed helpers, Ansible or a deliberate manual procedure from private
> `recovery/` inputs. Legacy archive keys are not a deployment dependency.

## 1. Select and render one environment

- [ ] Select **one** environment. Run DEV first, STAGE after DEV acceptance,
      and PROD after STAGE acceptance and explicit selection of existing PROD
      backend/frontend digests. Change only the first assignment when moving
      to the next environment:

```sh
environment=dev
case "$environment" in
  dev|stage) kubeconfig="$HOME/.kube/config-dev-stage" ;;
  prod) kubeconfig="$HOME/.kube/config-prod" ;;
  *) echo 'Choose dev, stage, or prod' >&2; exit 1 ;;
esac
namespace="app-$environment"
overlay="kubernetes/apps/liora/overlays/$environment"
render_dir="$PWD/.local-work/render/$environment"
recovery_dir="$HOME/fastapi-traefik-liora-infrastructure/recovery"
export environment kubeconfig namespace render_dir recovery_dir

mkdir -p .local-work
chmod 700 .local-work
kubectl --kubeconfig="$kubeconfig" config current-context
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
kubectl --kubeconfig="$kubeconfig" get storageclass
mkdir -p "$render_dir"
kubectl --kubeconfig="$kubeconfig" kustomize "$overlay" > "$render_dir/all.yaml"
```

- [ ] Match the API endpoint and nodes to the selected environment. DEV/STAGE
      must use `192.168.77.11:6443` and `k3s-1-01`–`03`; PROD must use
      `192.168.77.12:6443` and `k3s-2-01`–`03`. Confirm all nodes are Ready.
- [ ] Confirm the default `local-path` StorageClass and provisioner are
      Ready. Inspect images, Secret references, ConfigMaps, hosts, PVCs and
      replica counts in `$render_dir/all.yaml`. All application images must
      have pinned, real digests.

> [!WARNING]
> Stop on an API/node mismatch, a non-Ready node, missing storage, or an
> unconfigured/placeholder image.

CNPG requests one 2 GiB RWO volume for DEV and STAGE each, and two for PROD.
DEV/STAGE each have one backend/frontend replica; PROD has two of each.
Adminer keeps one replica. Existing database contents must survive routine
application updates; the separately authorized Phase 10 reset is exceptional.

All environments explicitly run one backend worker per Pod. The image defaults
to four workers; PROD's initial deployment repeatedly lost child workers before
becoming Ready, without recorded cgroup OOM kills. The single-worker command
matches the verified DEV/STAGE configuration. PROD still runs two backend Pods;
verify both replicas rather than relying on the worker count inside one Pod.

- [ ] Split the render into explicit application stages and reject
      unconfigured images before any cluster write:

```sh
python3 - <<'PY'
import os
from pathlib import Path
import yaml

root = Path(os.environ['render_dir'])
resources = list(yaml.safe_load_all((root / 'all.yaml').read_text()))
cnpg = any(r['kind'] == 'Cluster' and r['metadata']['name'] == 'liora-db' for r in resources)
private_adminer = any(r['kind'] == 'Service' and r['metadata']['name'] == 'adminer-private' for r in resources)
archive = any(r['kind'] == 'ObjectStore' and r['metadata']['name'] == 'r2-backup' for r in resources)
certificate = any(r['kind'] == 'Certificate' and r['metadata']['name'] == 'app-tls' for r in resources)
assert len(resources) == (11 if cnpg else 13) + int(private_adminer) + int(archive) + int(certificate)
assert {r['metadata']['namespace'] for r in resources} == {os.environ['namespace']}
groups = {name: [] for name in ['config-storage', 'database', 'prestart', 'application']}
for resource in resources:
    kind, name = resource['kind'], resource['metadata']['name']
    if kind in ['Deployment', 'Job']:
        for container in resource['spec']['template']['spec']['containers']:
            image = container['image']
            assert 'unconfigured' not in image and 'sha-' + '0' * 40 not in image, 'Select real images first'
            if name in ['backend', 'frontend', 'prestart']:
                assert '@sha256:' in image, 'Application images must be digest-pinned'
    if kind in ['ConfigMap', 'PersistentVolumeClaim', 'Certificate']:
        group = 'config-storage'
    elif (kind, name) in [('Service', 'db'), ('Deployment', 'postgres-deployment'), ('Cluster', 'liora-db'), ('ObjectStore', 'r2-backup')]:
        group = 'database'
    elif (kind, name) == ('Job', 'prestart'):
        group = 'prestart'
    else:
        group = 'application'
    groups[group].append(resource)
assert [len(groups[name]) for name in groups] == [(1 if cnpg else 3) + int(certificate), 2 + int(archive), 1, 7 + int(private_adminer)]
# The plugin configuration must exist before a Cluster requests WAL archiving.
groups['database'].sort(key=lambda r: r['kind'] != 'ObjectStore')
for name, items in groups.items():
    (root / (name + '.yaml')).write_text(yaml.safe_dump_all(items, sort_keys=False))
print('Render inspected and split; no resources applied')
PY
```

> [!TIP]
> You can run [the standalone split script](../../scripts/kubernetes/split-application-render.py)
> from the repository root with
> `python3 scripts/kubernetes/split-application-render.py` instead of the
> inline Python block.

- [ ] Confirm the split reports `Render inspected and split; no resources
      applied` before continuing.

## 2. Prepare the namespace and Secrets — Phase 2

> [!IMPORTANT]
> Run this section only after namespace and credential preparation is
> authorized. The render does not include Namespace or Secret objects.
> Each namespace needs independent `ghcr-pull-secret`, `backend-secrets`,
> and `db-secrets`. The backend's database password must agree with
> PostgreSQL's.

- [ ] Confirm the initial email in `backend-config` matches the local
      recovery record. The initial administrator password must be 8–40
      characters; use 32 random URL-safe characters for fresh lab accounts.
- [ ] For a **fresh database only**, create the namespace:

```sh
kubectl --kubeconfig="$kubeconfig" create namespace "$namespace" --dry-run=client -o yaml |
  kubectl --kubeconfig="$kubeconfig" apply -f -
```

> [!WARNING]
> The following bootstrap refuses to replace existing application Secrets
> or run when a PVC already exists. Existing deployments need their matching
> recovery values and a separate credential-rotation procedure. Changing
> PostgreSQL's Secret does not change an existing database password; prestart
> does not reset an existing administrator password. Do not use new lab
> credentials to recover an older database without reconciling its identities
> and passwords.

- [ ] Bootstrap the three application Secrets:

```sh
python3 - <<'PY'
import base64
import json
import os
from pathlib import Path
import shlex
import subprocess
import yaml

base = ['kubectl', '--kubeconfig=' + os.environ['kubeconfig'], '-n', os.environ['namespace']]
root = Path(os.environ['recovery_dir'])
entry = yaml.safe_load((root / 'recovery.yaml').read_text())['application_credentials'][os.environ['environment']]
assert entry['namespace'] == os.environ['namespace']
assert entry['first_superuser'] == 'admin007@liora.aprt.info'
assert entry['backend-secrets']['POSTGRES_PASSWORD'] == entry['db-secrets']['POSTGRES_PASSWORD']
for key in ['SECRET_KEY', 'FIRST_SUPERUSER_PASSWORD', 'POSTGRES_PASSWORD']:
    assert entry['backend-secrets'][key], 'Missing required credential'
assert 8 <= len(entry['backend-secrets']['FIRST_SUPERUSER_PASSWORD']) <= 40, 'Administrator password must be 8 to 40 characters'
registry = {}
for line in (root / '.env').read_text().splitlines():
    if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
        continue
    key, raw = line.removeprefix('export ').split('=', 1)
    values = shlex.split(raw, comments=True)
    if values:
        registry[key.strip()] = values[0]
assert registry['GHCR_REGISTRY'] == 'ghcr.io'
assert registry['GHCR_USERNAME'] and registry['GHCR_TOKEN']
required = {'ghcr-pull-secret', 'backend-secrets', 'db-secrets'}
existing = json.loads(subprocess.check_output(base + ['get', 'secrets', '-o', 'json']))
assert not required.intersection(s['metadata']['name'] for s in existing['items']), 'Existing application Secrets: preserve and review them'
claims = json.loads(subprocess.check_output(base + ['get', 'pvc', '-o', 'json']))
assert not claims['items'], 'Existing PVC: use the matching recovery procedure'
objects = []
for name in ['backend-secrets', 'db-secrets']:
    objects.append({'apiVersion': 'v1', 'kind': 'Secret',
                    'metadata': {'name': name, 'namespace': entry['namespace']},
                    'type': 'Opaque', 'stringData': entry[name]})
auth = base64.b64encode((registry['GHCR_USERNAME'] + ':' + registry['GHCR_TOKEN']).encode()).decode()
config = {'auths': {'ghcr.io': {'username': registry['GHCR_USERNAME'], 'password': registry['GHCR_TOKEN'], 'auth': auth}}}
objects.append({'apiVersion': 'v1', 'kind': 'Secret',
                'metadata': {'name': 'ghcr-pull-secret', 'namespace': entry['namespace']},
                'type': 'kubernetes.io/dockerconfigjson', 'stringData': {'.dockerconfigjson': json.dumps(config)}})
result = subprocess.run(base + ['apply', '--server-side', '--field-manager=liora-bootstrap', '-f', '-'],
                        input=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': objects}),
                        text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if result.returncode:
    raise SystemExit('Secret bootstrap failed; inspect permissions and conflicts without dumping values')
print('Three application Secrets created; values were not logged')
PY
```

> [!TIP]
> You can run [the standalone Secret bootstrap script](../../scripts/kubernetes/bootstrap-application-secrets.py)
> from the repository root with
> `python3 scripts/kubernetes/bootstrap-application-secrets.py` instead of the
> inline Python block.

- [ ] Check the Secret names and types:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get secrets
```

> [!NOTE]
> All three environments reference `app-tls`. Install the pinned cert-manager
> and Cloudflare DNS-01 issuer using [runbook 15](../../runbooks/15-publish-application.md)
> before applying the Certificate in the config/storage group. cert-manager
> issues a fresh certificate; a database restore does not require an old TLS
> private key. Traefik's fallback certificate does not verify trusted HTTPS.

### Check PVC provisioning before application deployment

After Secret bootstrap, test the default StorageClass in each target namespace
using the [temporary storage probe manifest](../../runbooks/_resources/application-storage-check.yaml).
The manifest has a 1Gi RWO claim with no explicit StorageClass, checking basic provisioning independently of CNPG's 2 GiB request, and a short-lived Pod that writes and reads a namespace
marker. It uses `postgres:16.6` to run a shell command; it does not start a
database or read application Secrets. The consumer Pod allows the
`WaitForFirstConsumer` claim to bind.

- [ ] With the environment selected in step 1, check for an existing probe.
      The first command below must show no existing resources. Stop if either
      name exists; do not replace an unrelated probe or delete any application
      PVC.

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pod,pvc liora-storage-check --ignore-not-found
```

- [ ] Only if neither resource exists, create the probe and check PVC
      binding, completed Pod, logs, PV and node:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" create -f runbooks/_resources/application-storage-check.yaml
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Bound pvc/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" logs liora-storage-check
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc liora-storage-check -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pod liora-storage-check -o wide
probe_pv=$(kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc liora-storage-check -o jsonpath='{.spec.volumeName}')
kubectl --kubeconfig="$kubeconfig" get pv "$probe_pv" -o wide
```

- [ ] Confirm `local-path`, PVC Bound, Pod Succeeded, and the expected
      namespace marker in the logs. DEV/STAGE must use a `k3s-1-` node; PROD
      must use a `k3s-2-` node. Record the actual PV and node.

> [!NOTE]
> The probe verifies provisioning and basic file I/O. It does not verify
> backup restoration, node failure recovery, database behavior, or storage
> redundancy.

- [ ] After recording a successful check, remove **only** the temporary
      probe resources and wait for their PV to be reclaimed:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" delete pod/liora-storage-check pvc/liora-storage-check --wait=true
kubectl --kubeconfig="$kubeconfig" wait --for=delete "pv/$probe_pv" --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pods,pvc
```

### If the storage probe fails

> [!WARNING]
> Inspect events and Pod status before cleanup. Investigate and repeat the
> probe; record transient interruptions. Do not proceed until a fresh check
> passes. CNPG creates its own instance PVCs during deployment; the probe does not
> pre-create them.

## 3. Bring up PostgreSQL, then prestart

- [ ] First install the pinned operator and provision `cnpg-app` and
      `cnpg-superuser` following [runbook 18](../../runbooks/18-cloudnative-pg.md). Existing
      Argo-owned environments must use their reviewed GitOps sync, not these
      manual fresh-bootstrap apply commands.
- [ ] For the current authorized environment only, apply configuration and
      database resources. Wait for CNPG readiness and every requested instance:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/config-storage.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/database.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=condition=Ready cluster/liora-db --timeout=600s
expected_instances=1
if [ "$environment" = prod ]; then expected_instances=2; fi
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.readyInstances}'="$expected_instances" cluster/liora-db --timeout=600s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get cluster,pvc -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get job prestart --ignore-not-found
```

- [ ] Inspect the bound PV's node affinity and actual StorageClass.

> [!NOTE]
> A Pending PVC before a database Pod exists is expected with
> `WaitForFirstConsumer`; wait for Bound only after creating the database
> Cluster. Local-path volume contents are node-local; CNPG streaming replication
> provides database replication separately across
> K3s servers.

- [ ] Confirm `prestart` is absent for a fresh install. On a redeploy, review
      the old Job, image changes, database backup, and migration behavior
      before deliberately recreating it.

> [!WARNING]
> An earlier Complete Job does not prove that the new image's migrations
> ran. Job templates are immutable. Do not delete PVCs to retry a Job.

- [ ] After PostgreSQL is Ready, apply `prestart` and wait for Complete:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/prestart.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=condition=complete job/prestart --timeout=660s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get job prestart
```

### If prestart fails

> [!WARNING]
> Stop before applying the application group. Inspect Job events and logs
> privately; review logs before sharing them. Fix the database, image, or
> credential problem before retrying.

> [!NOTE]
> Direct `kubectl apply` does **not** implement Argo CD sync-wave or hook
> ordering, cleanup, or recreation. Applying the whole overlay at once
> bypasses these gates.

## 4. Start the remaining workloads

- [ ] Only after `prestart` completes, apply the remaining workloads and
      wait for backend, frontend, and Adminer rollouts:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/application.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/backend --timeout=240s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/frontend --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/adminer --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployments,pods,pvc,jobs,ingress
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployments -o 'custom-columns=NAME:.metadata.name,IMAGES:.spec.template.spec.containers[*].image'
```

- [ ] Record the reviewed Git commit, deployment images, actual Pod image IDs,
      PVC/PV binding, namespace, and cluster.

> [!NOTE]
> A rollout alone is not an application acceptance check. Complete the
> environment-specific checks in step 5.

## 5. Private acceptance, separately for every environment

- [ ] In a separate terminal on VM 200, select the **same** environment as in
      step 1 and start a localhost-only ingress forward:

```sh
kubectl --kubeconfig="$kubeconfig" -n kube-system port-forward --address=127.0.0.1 service/traefik 18080:80
```

- [ ] In the original terminal, check the selected hostname's backend health
      and frontend through that forward:

```sh
case "$environment" in
  dev) hostname=dev.liora.aprt.info ;;
  stage) hostname=stage.liora.aprt.info ;;
  prod) hostname=liora.aprt.info ;;
esac
curl --fail --silent --show-error -H "Host: $hostname" http://127.0.0.1:18080/api/v1/utils/health-check/
curl --fail --silent --show-error -H "Host: $hostname" --output /dev/null http://127.0.0.1:18080/
```

- [ ] For browser acceptance from the trusted workstation, tunnel VM 200's
      loopback port to the workstation, map the selected hostname to
      `127.0.0.1` in the workstation's hosts file, and open
      `http://<selected-hostname>:18080`. Keep the tunnel and forward private.
- [ ] Log in as `admin007@liora.aprt.info` using that environment's recovery
      password. Create, read, edit, and read back an item titled
      `acceptance-<environment>-<date>`. Retain this synthetic marker for
      the next environment's isolation check. Do not use real personal data.

> [!NOTE]
> This is a temporary HTTP test path; canonical STAGE/PROD frontend URLs
> remain HTTPS. The frontend must call relative `/api` routes through this
> ingress. Forwarding the frontend Service alone does not route API calls.
> This test does not establish public routing, canonical-origin CORS, or TLS
> acceptance.

### If the browser requires HTTPS

> [!WARNING]
> Establish trusted private TLS for that hostname and record browser
> acceptance as pending until it is available.

### Automated browser acceptance alternative

> [!TIP]
> The standalone browser check is an alternative to the manual login and
> item actions above. It uses the same exported `environment`, `namespace`,
> `recovery_dir`, and `render_dir`. It resolves the selected hostname to
> loopback inside Chromium; no hosts-file or public DNS change is needed.
> It still tests the temporary private HTTP origin.

- [ ] If using the automated alternative, keep the ingress forward running.
      Install the browser tooling on the machine running the check, then run
      the verification script:

```sh
mkdir -p .local-work
chmod 700 .local-work
python3 -m venv .local-work/venv
.local-work/venv/bin/python -m pip install -r scripts/requirements-local-tools.txt
bash scripts/local-python.sh -m playwright install --with-deps chromium
bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
```

If the checkout's tools are already prepared, run only the last command.
See the [local workspace guide](../../runbooks/11-install-management-tools.md#operator-python-and-browser-tools) for paths and the
existing lab's browser libraries.

The [browser verification script](../../scripts/kubernetes/verify-application-ui.py)
can also be copied to VM 200 and run with the prepared Python environment.
Installing Chromium system libraries requires package-management privileges;
use the manual browser procedure if those are unavailable.

> [!NOTE]
> The script verifies health, UI login, item creation/editing, page reload,
> and persistence through the authenticated API. It writes the marker ID,
> title, and result to `$render_dir/acceptance.json` for the next phase.
> It does not save passwords, tokens, browser state, or traces.

### If the browser check fails or is repeated

> [!WARNING]
> A failed run reports its step and error type. If it created an item, use
> the recorded ID to review or remove only that marker before retrying.
> Repeated successful checks create additional markers; retain their records
> or clean up those markers first.

### Acceptance gates

#### DEV — Phase 3

- [ ] `app-dev` Pods run on `k3s-1-` nodes; PVC Bound; PostgreSQL Ready;
      `prestart` Complete; backend, frontend, and Adminer Ready.
- [ ] Health, UI login, and DEV item create/read/update pass. Record exact
      images and retain the DEV marker.

#### STAGE — Phase 4

- [ ] `app-stage` Pods run on `k3s-1-` nodes and pass every DEV workload,
      health, UI, and data check with STAGE credentials.
- [ ] STAGE has a distinct PVC/PV. The DEV marker is absent from STAGE, the
      STAGE marker is absent from DEV, and DEV remains healthy.

#### PROD — Phase 5

- [ ] `app-prod` Pods run on `k3s-2-` nodes with approved real digests and
      two Ready backend and two Ready frontend replicas.
- [ ] PROD passes the workload, health, UI, and data checks. Its database
      contains neither nonprod marker; DEV and STAGE remain healthy.

### Close out each environment

- [ ] Verify the actual Pod nodes:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-dev get pods -o wide
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-stage get pods -o wide
kubectl --kubeconfig="$HOME/.kube/config-prod" -n app-prod get pods -o wide
```

- [ ] Complete each environment's report before the next deployment phase.
      Retain DEV and STAGE markers through Phase 5; after all isolation
      checks pass, delete only your acceptance items and confirm removal.

> [!NOTE]
> Check Adminer through a private Service forward if needed; it has no
> public ingress. Trusted HTTPS and canonical URL checks wait for the
> required certificate, DNS/private host resolution, and routing.

## If restoring data or rolling back

> [!IMPORTANT]
> Applying these manifests to a fresh recovery cluster creates an empty
> database; it **does not restore application data**. Use the matching backup,
> credentials, and signing key. A new administrator password in recovery YAML
> does not reset an account in a restored database.

- [ ] Before recovery, select and verify the matching database backup,
      restoration point, database credentials, and signing key.
- [ ] Restore and validate data using the separate tested PostgreSQL restore
      procedure **before** migrations or application writes. Preserve the
      matching recovery material.
- [ ] Before changing application schema, back up and test restoration.

> [!WARNING]
> Reverting an image digest does not undo a prestart database migration.
> Never delete a PVC, namespace, or local-path volume as an application
> rollback step: the StorageClass has reclaim policy `Delete`. Argo CD
> retention annotations do not protect against a direct `kubectl delete`.

## Next: GitOps ownership

After independent environment acceptance, continue with
[runbook 14: separate Argo CD instances](../../runbooks/14-install-argocd.md) during authorized
Phase 6. The completed installation and reconciliation results are recorded in
the [Phase 6 report](PHASE6_REPORT.md). Keep manual deployment
and controller ownership checks distinct during fresh recovery.
