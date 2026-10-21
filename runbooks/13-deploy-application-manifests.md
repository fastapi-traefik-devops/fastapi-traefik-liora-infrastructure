# Deploy and verify the application manifests

**Where:** Management VM 200, from the reviewed infrastructure checkout.

**Status:** Phase 1 has imported and rendered these manifests locally. No
application deployment or acceptance on the new K3s clusters has been verified.
PROD is pinned to the operator-approved STAGE image pair `sha-c375967...`.
Phase 2 namespace/Secret preparation and temporary storage checks are verified
for all three environments; see the [Phase 2 report](../kubernetes/PHASE2_REPORT.md).
Application deployment begins separately in Phase 3.
These commands are the procedure for later authorized phases; importing the
files does not authorize running them.

## Scope and prerequisites

Retain PostgreSQL 16.6, its 1Gi PVC, Adminer 4.8.1, and the prestart migration
Job. This procedure does not install Argo CD, monitoring, CloudNativePG, edge
routing, DNS, or certificate automation. Preserve each environment's data.

| Environment | Kubeconfig | Namespace | Configured origin |
| --- | --- | --- | --- |
| DEV | `$HOME/.kube/config-dev-stage` | app-dev | `http://dev.liora.aprt.info` |
| STAGE | `$HOME/.kube/config-dev-stage` | app-stage | `https://stage.liora.aprt.info` |
| PROD | `$HOME/.kube/config-prod` | app-prod | `https://liora.aprt.info` |

DEV currently keeps the source's HTTP ingress and `ENVIRONMENT: staging`.
STAGE/PROD retain HTTPS settings and reference a namespace-local `app-tls`
Secret. Setting these hostnames does not configure DNS, certificates, or public
access. A trusted HTTPS check needs a matching certificate and private ingress
path; otherwise record it as pending. API VIPs are not dedicated ingress VIPs.

Require `kubectl`, Python 3 with PyYAML (`python3 -c 'import yaml'`), access to
both explicit kubeconfigs, and the reviewed Git revision. Each Python block
below also links to a standalone script. Use either the inline block or its
script file; both use the environment variables exported in step 1. You can
copy a script to VM 200 and run it with `python3 /path/to/script.py`, or run
the repository copy using the command beside its link.

The default kubeconfig points to the separate kind reference cluster; never
rely on it for K3s.

Recovery inputs currently reside in the **original checkout**, not the migration
worktree:

- `$HOME/fastapi-traefik-liora-infrastructure/recovery/recovery.yaml`:
  `application_credentials.<environment>` holds `first_superuser`, namespace,
  `backend-secrets`, and `db-secrets`. The initial account is
  `admin007@liora.aprt.info` in each separate database.
- `$HOME/fastapi-traefik-liora-infrastructure/recovery/.env`:
  `GHCR_REGISTRY`, `GHCR_USERNAME`, and `GHCR_TOKEN` supply registry read access.

Keep both files ignored and mode `0600`; include them in the operator's external
recovery archive. Do not print values, use shell tracing, put credentials in
command arguments, or commit generated Secret manifests. Old Sealed Secrets
controller keys in the recovery YAML are not required by this manual bootstrap.

## 1. Select and render one environment

Run DEV first, STAGE after DEV acceptance, and PROD after STAGE acceptance and
explicit selection of existing PROD backend/frontend digests. Change only the
first assignment when moving to the next environment:

```sh
environment=dev
case "$environment" in
  dev|stage) kubeconfig="$HOME/.kube/config-dev-stage" ;;
  prod) kubeconfig="$HOME/.kube/config-prod" ;;
  *) echo 'Choose dev, stage, or prod' >&2; exit 1 ;;
esac
namespace="app-$environment"
overlay="kubernetes/apps/liora/overlays/$environment"
render_dir="$HOME/liora-render/$environment"
recovery_dir="$HOME/fastapi-traefik-liora-infrastructure/recovery"
export environment kubeconfig namespace render_dir recovery_dir

kubectl --kubeconfig="$kubeconfig" config current-context
kubectl --kubeconfig="$kubeconfig" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$kubeconfig" get nodes -o wide
kubectl --kubeconfig="$kubeconfig" get storageclass
mkdir -p "$render_dir"
kubectl --kubeconfig="$kubeconfig" kustomize "$overlay" > "$render_dir/all.yaml"
```

Expect DEV/STAGE at `192.168.77.11:6443` with `k3s-1-01`–`03`, and PROD at
`192.168.77.12:6443` with `k3s-2-01`–`03`. Stop on a mismatch or non-Ready node.
The default `local-path` StorageClass must be present and its provisioner Ready.
Each environment needs one 1Gi RWO PVC; DEV/STAGE each have one backend and one
frontend replica, while PROD has two of each. PostgreSQL and Adminer each have
one replica. Inspect images, Secret references, ConfigMaps, hosts and PVCs in
the rendered file. All three overlays have pinned application digests. Never
deploy placeholders introduced by a later edit.

Split the render into explicit application stages, rejecting unconfigured
images before any cluster write:

```sh
python3 - <<'PY'
import os
from pathlib import Path
import yaml

root = Path(os.environ['render_dir'])
resources = list(yaml.safe_load_all((root / 'all.yaml').read_text()))
assert len(resources) == 13
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
    if kind in ['ConfigMap', 'PersistentVolumeClaim']:
        group = 'config-storage'
    elif (kind, name) in [('Service', 'db'), ('Deployment', 'postgres-deployment')]:
        group = 'database'
    elif (kind, name) == ('Job', 'prestart'):
        group = 'prestart'
    else:
        group = 'application'
    groups[group].append(resource)
assert [len(groups[name]) for name in groups] == [3, 2, 1, 7]
for name, items in groups.items():
    (root / (name + '.yaml')).write_text(yaml.safe_dump_all(items, sort_keys=False))
print('Render inspected and split; no resources applied')
PY
```

Standalone script: [Split the rendered manifests](../scripts/kubernetes/split-application-render.py).
From the repository root, run `python3 scripts/kubernetes/split-application-render.py`.

## 2. Prepare the namespace and Secrets — Phase 2

Run only after namespace/credential preparation is authorized. The render does
not include Namespace or Secret objects. Each namespace needs independent
`ghcr-pull-secret`, `backend-secrets`, and `db-secrets`. The backend's database
password must agree with PostgreSQL's. Verify the initial email in
`backend-config` matches the local recovery record.

For a **fresh database only**, create the namespace:

```sh
kubectl --kubeconfig="$kubeconfig" create namespace "$namespace" --dry-run=client -o yaml |
  kubectl --kubeconfig="$kubeconfig" apply -f -
```

The following bootstrap refuses to replace existing application Secrets or run
when a PVC already exists. Existing deployments need their matching recovery
values and a separate credential-rotation procedure. Changing PostgreSQL's
Secret does not change an existing database password; prestart does not reset
an existing administrator password. Do not use the new lab credentials to
recover an older database without reconciling its identities and passwords.

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

Standalone script: [Bootstrap the application Secrets](../scripts/kubernetes/bootstrap-application-secrets.py).
From the repository root, run `python3 scripts/kubernetes/bootstrap-application-secrets.py`.

Then check the Secret names and types:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get secrets
```

STAGE/PROD additionally reference `app-tls`. Restore an appropriate certificate
and private key as a namespace-local TLS Secret through a separately authorized
procedure before trusted HTTPS acceptance. Do not mistake Traefik's fallback
certificate for verification. Private HTTP ingress checks below do not verify TLS.

### Verify PVC provisioning before application deployment

After Secret bootstrap, test the default StorageClass in each target namespace
using the [temporary storage probe manifest](_resources/application-storage-check.yaml).
The manifest has a 1Gi RWO claim with no explicit StorageClass, matching the
application's request, and a short-lived Pod that writes and reads a namespace
marker. It uses `postgres:16.6` to run a shell command; it does not start a
database or read application Secrets. The consumer Pod allows the
`WaitForFirstConsumer` claim to bind.

Run the following separately with the DEV, STAGE and PROD selection from step 1.
The first command must show no existing resources; stop if either name already
exists. Do not replace an unrelated probe or delete any application PVC.

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pod,pvc liora-storage-check --ignore-not-found
kubectl --kubeconfig="$kubeconfig" -n "$namespace" create -f runbooks/_resources/application-storage-check.yaml
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Bound pvc/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/liora-storage-check --timeout=300s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" logs liora-storage-check
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc liora-storage-check -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pod liora-storage-check -o wide
probe_pv=$(kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc liora-storage-check -o jsonpath='{.spec.volumeName}')
kubectl --kubeconfig="$kubeconfig" get pv "$probe_pv" -o wide
```

Require `local-path`, claim status Bound, Pod status Succeeded, and the expected
namespace marker in the logs. DEV/STAGE must use a `k3s-1-` node; PROD must use a
`k3s-2-` node. Record the actual PV and node. This verifies provisioning and
basic file I/O, not backup restoration, node failure recovery, database behavior
or storage redundancy.

After recording a successful check, remove only these temporary resources and
wait for their dynamically provisioned PV to be reclaimed:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" delete pod/liora-storage-check pvc/liora-storage-check --wait=true
kubectl --kubeconfig="$kubeconfig" wait --for=delete "pv/$probe_pv" --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pods,pvc
```

If the check fails, inspect its events and Pod status before cleanup and report
the failure. Investigate the cause, then repeat the probe; record any transient
runtime interruption and retry. Do not move on until a fresh check passes;
recurring failures need resolution before deployment.
The application `postgres-vol` PVC is created separately during its deployment
phase; a successful probe does not pre-create it.

## 3. Bring up PostgreSQL, then prestart — Phases 3, 4 or 5

For the current authorized environment only:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/config-storage.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/database.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=jsonpath='{.status.phase}'=Bound pvc/postgres-vol --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/postgres-deployment --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" exec deployment/postgres-deployment -- sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get pvc postgres-vol -o wide
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get job prestart --ignore-not-found
```

A Pending PVC before a database Pod exists is expected with
`WaitForFirstConsumer`; wait for Bound only after creating the database
Deployment. Inspect the bound PV's node affinity and actual StorageClass.
Local-path data is node-local and is not replicated across K3s servers.

For a fresh install, `prestart` must be absent. On a redeploy, review the old
Job, image changes, database backup and migration behavior before deliberately
recreating it. Do not treat an earlier Complete Job as proof that the new image's
migrations ran; Job templates are immutable. Do not delete PVCs to retry a Job.

After confirming PostgreSQL is Ready, apply the Job and wait:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/prestart.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" wait --for=condition=complete job/prestart --timeout=660s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get job prestart
```

If it fails, stop before applying the application group. Inspect Job events and
logs privately; logs can contain operational details and must be reviewed
before sharing. Fix the underlying database, image or credential problem.
Direct `kubectl apply` does **not** implement Argo CD sync-wave or hook ordering,
cleanup, or recreation. Applying the whole overlay at once would bypass these
explicit gates.

## 4. Start the remaining workloads

Only after prestart completes:

```sh
kubectl --kubeconfig="$kubeconfig" -n "$namespace" apply -f "$render_dir/application.yaml"
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/backend --timeout=240s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/frontend --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" rollout status deployment/adminer --timeout=180s
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployments,pods,pvc,jobs,ingress
kubectl --kubeconfig="$kubeconfig" -n "$namespace" get deployments -o 'custom-columns=NAME:.metadata.name,IMAGES:.spec.template.spec.containers[*].image'
```

Record the reviewed Git commit, deployment images, actual Pod image IDs, PVC/PV
binding, namespace, cluster and acceptance results. A rollout alone is not an
application acceptance check.

## 5. Private acceptance, separately for every environment

Use a localhost-only ingress forward on VM 200 in a separate terminal. Set the
same environment selection variables there first. No public DNS change is
needed for command-line checks:

```sh
kubectl --kubeconfig="$kubeconfig" -n kube-system port-forward --address=127.0.0.1 service/traefik 18080:80
```

In the original terminal:

```sh
case "$environment" in
  dev) hostname=dev.liora.aprt.info ;;
  stage) hostname=stage.liora.aprt.info ;;
  prod) hostname=liora.aprt.info ;;
esac
curl --fail --silent --show-error -H "Host: $hostname" http://127.0.0.1:18080/api/v1/utils/health-check/
curl --fail --silent --show-error -H "Host: $hostname" --output /dev/null http://127.0.0.1:18080/
```

For browser acceptance from the trusted workstation, tunnel the management
VM's loopback port to the workstation, map the selected hostname to
`127.0.0.1` in the workstation's hosts file, and open
`http://<selected-hostname>:18080`. Keep the tunnel and forward private. This is
a temporary HTTP test path; canonical STAGE/PROD frontend URLs remain HTTPS.
The frontend must call relative `/api` routes through this same ingress;
forwarding the frontend Service alone does not route API calls. If the browser
requires HTTPS for the domain, establish trusted private TLS instead and record
browser acceptance as pending until that path is available. Do not claim public
routing, canonical-origin CORS, or TLS acceptance from this temporary path.

Log in as `admin007@liora.aprt.info` using that environment's local recovery
password. Create and read back an item titled `acceptance-<environment>-<date>`;
edit it and read it again. Retain the environment marker temporarily to check
isolation when the next environment is deployed. Do not use real personal data.

| Gate | Required checks before proceeding |
| --- | --- |
| DEV / Phase 3 | app-dev runs on k3s-1 nodes; PVC Bound; PostgreSQL Ready; prestart Complete; backend/frontend/Adminer Ready; health and UI login pass; DEV item write/read/update passes; record exact images |
| STAGE / Phase 4 | app-stage runs on k3s-1 nodes; repeat every DEV check with STAGE credentials; its PVC/PV is distinct; DEV marker is absent from STAGE; STAGE marker is absent from DEV; DEV remains healthy |
| PROD / Phase 5 | approved real digests, no placeholders; app-prod runs on k3s-2 nodes; two backend and two frontend replicas Ready; repeat all data and UI checks; its database contains neither nonprod marker; DEV/STAGE remain healthy |

After checking isolation in both directions, delete only the acceptance items
you created and confirm their removal. Check Adminer through a private Service
forward if needed; it has no public ingress. Verify the actual Pod nodes with:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-dev get pods -o wide
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n app-stage get pods -o wide
kubectl --kubeconfig="$HOME/.kube/config-prod" -n app-prod get pods -o wide
```

Complete each environment's report before the next deployment phase. Keep
trusted HTTPS and canonical URL checks separate until the required certificate,
DNS/private host resolution and routing are available.

## Disaster recovery and rollback boundary

Applying these manifests to a fresh recovery cluster creates an empty database;
it **does not restore application data**. Before recovery, select and verify the
matching database backup, restoration point, database credentials and signing
key. Data restoration needs its own tested PostgreSQL restore procedure and
validation before running migrations or allowing application writes. A new
administrator password in recovery YAML does not reset an account in a restored
database. Do not overwrite the matching recovery material with newly generated
values.

Back up and test restoration before changing application schema. Reverting an
image digest does not undo a prestart database migration. Never delete a PVC,
namespace or local-path volume as an application rollback step; the StorageClass
has reclaim policy `Delete`. Argo CD retention annotations have no protective
effect on a direct `kubectl delete` command.
