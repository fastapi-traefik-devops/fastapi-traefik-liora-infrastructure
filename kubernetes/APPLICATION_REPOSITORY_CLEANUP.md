# Application repository cleanup candidates

Source reviewed: `fastapi-traefik-devops/fastapi-traefik-liora-application`
at upstream `b98a22e48527c256193ed65c10307eb574b27ab6`
(initial local review: `1a5b24f096dd1a6234fa101f8648e40db88b52c7`).

This is a future ownership checklist, not deletion authorization. No application
files have been changed. The selected deployment history is imported on the
isolated migration branch, but K3s acceptance and promotion migration are still
pending. Remove a path only after its replacement has been migrated, tested,
reviewed, and all consumers have been updated.

| Application path | Earliest condition for removal or ownership review |
| --- | --- |
| `deploy/base/` | History-preserving import and acceptance of all three infrastructure-owned deployments |
| `deploy/overlays/dev/`, `deploy/overlays/stage/`, `deploy/overlays/prod/` | Verified infrastructure overlays, promotion changes, and tested rollback; retain promotion-record provenance |
| `argocd/` | Separate nonprod/prod Argo CD instances use this infrastructure repository; review ApplicationSet consumers first |
| `monitoring/` | Both clusters' monitoring and operational access are migrated and verified |
| `Jenkinsfile.promote` | Reviewed infrastructure digest-promotion workflow replaces all callers |
| `ci/promote.py`, `ci/promote-stage.sh`, `ci/publish.sh`, `ci/registry.py` | Review responsibility and callers during Phase 9; image publication stays application-owned, so shared build helpers may need to remain |
| `k8s/` | Confirm historical references have no active consumers; do not import as the active deployment |
| `infra/jenkins-host/` | Separate CI-placement and recovery review; no migration or removal in this increment |

Keep application code, tests, image builds, release tags, and the image-publishing
Jenkins pipeline in the application repository. Audit documentation and script
references before removing infrastructure paths. Never move `.env` files,
private keys, Terraform state, or live credentials into tracked infrastructure
files. Later infrastructure imports require the same selective history and
credential review as the deployment import.
