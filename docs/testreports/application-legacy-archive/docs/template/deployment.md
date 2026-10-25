# Argo CD deployment

The production path is [GitHub Flow + Jenkins + GHCR + Argo CD](../../infra/jenkins-host/README.md).
Jenkins never applies application resources. Git `main`, `deploy/overlays/{dev,stage,prod}`,
is desired state. `k8s/` is a retained legacy example, not an active deployment root.
Do not apply both manifest trees to the same workload. Compose remains a separate
local development tool, not this project's production CD system.

## One-time operator bootstrap

Do not run these steps until the changes have been reviewed/merged, Jenkins trust
boundaries configured, and real hostnames/secrets/storage prepared. These commands
are instructions only; no real cluster was changed during implementation.

1. Install a supported, organization-approved Argo CD version, including its
   ApplicationSet controller, or connect to your existing installation. Download
   and review the exact release manifests (never an unpinned `stable` URL), e.g.:

   ```bash
   export ARGOCD_VERSION='<approved-version>'
   curl -fL "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml" -o /tmp/argocd-install.yaml
   # Review the downloaded manifest before the next commands.
   kubectl create namespace argocd
   kubectl apply -n argocd -f /tmp/argocd-install.yaml
   ```

   Skip installation if Argo already exists. Configure SSO/RBAC and restrict
   Application/AppProject writes and sync overrides to platform administrators.
   Ordinary users must not override main, image parameters or the production
   source path. Register a read-only repository credential in Argo for private Git.
2. Create `app-dev`, `app-stage`, `app-prod` namespaces outside the ApplicationSet:

   ```bash
   kubectl create namespace app-dev
   kubectl create namespace app-stage
   kubectl create namespace app-prod
   ```

   Provision `backend-secrets`, `db-secrets`, `ghcr-pull-secret`, and `app-tls`
   securely in each namespace. See the exact key/permission table in
   infra/jenkins-host/README.md. Use an external secret manager or newly sealed namespace-
   specific secrets; never commit generated plaintext YAML. Configure Traefik,
   DNS and valid TLS certificates for real hosts replacing `*.example.com` in
   overlays. The AppProject cannot create Namespaces, Secrets or cluster RBAC.
3. Choose the cluster's storage class and capacity, backup/restore and database
   ownership. The base retains a 1Gi default-class RWO PVC and a single PostgreSQL
   Deployment using Recreate to avoid concurrent writers. PVC deletion/pruning
   is disabled in Argo annotations; do not assume this substitutes for backups.
   Migrating existing `dev` data into `app-dev` requires an explicit operator data
   migration plan. No existing namespace/data is adopted or deleted automatically.
4. Complete the Jenkins setup, publish real images, and promote dev/stage. Initial
   overlay tags are deliberately all-zero SHA placeholders and will not pull.
   Before enabling each Argo application, replace that environment's placeholder
   through its normal promotion flow; production still needs a reviewed release.
   For phased bootstrap, temporarily list only provisioned environments in the
   ApplicationSet through a reviewed Git change, adding prod after approval.
5. Review and apply the AppProject/ApplicationSet as an administrator:

   ```bash
   kubectl apply -f argocd/project.yaml
   kubectl apply -f argocd/applicationset.yaml
   ```

   They define `app-dev`, `app-stage`, `app-prod` against the in-cluster API,
   tracking only this repository's main. All automatically sync, prune and
   self-heal **after** Git approval. For an external cluster update both
   destination definitions and register that cluster with Argo first.
6. Verify actual Argo sync/health, image digests and migrations in dev/stage before
   production. Set up alerting for failed hooks, sync failures and missing Secrets.
   Normal subsequent application deployment requires only Git changes.

## Rollback

Revert the offending overlay promotion commit in a reviewed PR, restoring both
`kustomization.yaml` SHA/digests and `promotion.json` together, or explicitly set
both to a previously recorded artifact pair. Merge to main; Argo detects the
reverted desired state and reconciles it. No image rebuild or Jenkins cluster
command is needed. A new main build can subsequently advance stage again.

For production, review the rollback PR under the same rules as a release. Avoid
Argo UI rollback/parameter overrides while auto-sync is enabled: Git would restore
the declared state. Database migrations are not automatically reversible; verify
schema compatibility before reverting application images and use your separately
approved restore/migration procedure when necessary. Keep old image digests in GHCR.

## References

- [Argo sync phases/waves and hooks](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
- [Jenkins credentials and untrusted pipelines](https://www.jenkins.io/doc/book/pipeline/jenkinsfile/)
- [GHCR digest-based pulls](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
