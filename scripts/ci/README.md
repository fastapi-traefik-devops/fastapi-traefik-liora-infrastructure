# GitOps validation

`validate-gitops.sh` renders the actual infrastructure overlays and checks that
both application images are canonical, digest-pinned, non-placeholder references
to the same source SHA. It uses strict kubeconform when installed; set
`REQUIRE_KUBECONFORM=1` to fail if it is missing, as the PR workflow does.
Missing schemas and malformed resources fail validation; no kinds are skipped.
It never reads kubeconfig or accesses a cluster.

Kubeconform searches committed `crd-*.json` schemas beside the script, then its
standard Kubernetes schema catalog (currently Kubernetes 1.35.0). No sibling
application checkout is needed. Standard schemas normally require network access
on first use. Set `KUBECONFORM_CACHE` to a previously populated kubeconform cache
for offline runs; otherwise a temporary cache is removed on exit. An empty cache
is not sufficient for offline validation of standard Kubernetes resources.

`validate_gitops.py` matches the reviewed application trusted publisher validator;
update both deliberately when changing their shared admission rules.

`install-validation-tools.py DIRECTORY` installs only kustomize and kubeconform
using release checksums copied from the application's existing tool lock.
Put the installed directory on `PATH`; Python needs PyYAML (CI pins 6.0.3).
No scanners are installed or executed. The PR workflow has read-only repository
access and no deployment credentials. It runs the regression tests below before
strict validation of all three environments. Vendored operator bundle changes
also trigger the workflow so schema drift is checked.

```sh
python3 -B -m unittest discover -s scripts/ci -p 'test_*.py'
REQUIRE_KUBECONFORM=1 sh scripts/ci/validate-gitops.sh
```

The tests require kubeconform and check all three real custom resources, unknown
fields, incorrect field types and missing API-version schemas without network
access. They also regenerate schemas in memory to verify exact correspondence
with vendored served API versions. Existing image-reference tests remain intact.

## Schema provenance and updates

The converter follows the companion application repository's `ci/crd_schema.py`
approach: remove descriptions, reject unknown properties on structured objects,
preserve explicitly free-form fields, and normalize nullable/int-or-string fields.
Here it reads the already-vendored release bundles rather than live CRDs.
Each schema's `$comment` records the CRD name, served version and SHA-256 of the
source OpenAPI schema. Release origins and bundle checksums are recorded in each
operator directory's `UPSTREAM.md`.

| Resource API | Vendored release source under `kubernetes/platform/` |
| --- | --- |
| `cert-manager.io/v1`, `Certificate` | `cert-manager/upstream/cert-manager-1.21.2.yaml` |
| `postgresql.cnpg.io/v1`, `Cluster` | `cloudnative-pg/upstream/cnpg-1.30.1.yaml` |
| `barmancloud.cnpg.io/v1`, `ObjectStore` | `barman-cloud/upstream/barman-cloud-0.15.1.yaml` |

All three APIs match the application manifests. Regenerate from the repository
root after reviewing an operator release upgrade or resource API-version change:

```sh
python3 scripts/ci/crd_schema.py kubernetes/platform/cert-manager/upstream/cert-manager-1.21.2.yaml Certificate v1
python3 scripts/ci/crd_schema.py kubernetes/platform/cloudnative-pg/upstream/cnpg-1.30.1.yaml Cluster v1
python3 scripts/ci/crd_schema.py kubernetes/platform/barman-cloud/upstream/barman-cloud-0.15.1.yaml ObjectStore v1
```

Update these source paths and `test_crd_schema.py`'s release cases when versions
change. Review the generated diff and provenance hashes, then run the tests and
strict validation above. Commit the schemas together with the corresponding
operator/API changes. No cluster exports or credentials are required.

Kubeconform checks JSON-schema constraints, not admission webhooks, CEL rules or
runtime operator behavior; passing does not establish that a deployment works.
