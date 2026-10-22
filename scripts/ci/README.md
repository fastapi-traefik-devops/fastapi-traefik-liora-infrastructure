# Prepared GitOps validation

`validate-gitops.sh` renders the actual infrastructure overlays and checks that
both application images are canonical, digest-pinned, non-placeholder references
to the same source SHA. It uses strict kubeconform when installed; set
`REQUIRE_KUBECONFORM=1` to fail if it is missing. It never accesses a cluster.
`validate_gitops.py` matches the reviewed application trusted publisher validator;
update both deliberately when changing their shared admission rules.

`install-validation-tools.py DIRECTORY` installs only kustomize and kubeconform
using release checksums copied from the application's existing tool lock.
No scanners are installed or executed. The prepared PR workflow has read-only
repository access and no deployment credentials. It is useful later but is not
a dependency of the initial Jenkins/STAGE activation path.

```sh
python3 -B -m unittest discover -s scripts/ci -p 'test_*.py'
sh scripts/ci/validate-gitops.sh
```
