# CloudNativePG operator

Official release: [v1.30.1](https://github.com/cloudnative-pg/cloudnative-pg/releases/tag/v1.30.1).
The unchanged vendored `upstream/cnpg-1.30.1.yaml` was downloaded from the
release asset `cnpg-1.30.1.yaml`; SHA-256:
`37237f145d8138256ea25ae830f87759255665ff08f8d552fdd8224a5ec032fb`.
Kustomize pins the operator image by release tag and OCI index digest and bounds
its resources. `OPERATOR_IMAGE_NAME` uses the same digest so generated instance
bootstrap containers are reproducible too. Install independently in both clusters using server-side apply.
The platform operator is operator-managed infrastructure, not owned by the
application Argo projects. Environment Cluster objects are application-owned.

The [1.30 support table](https://cloudnative-pg.io/docs/1.30/supported_releases/)
covers Kubernetes 1.36 and PostgreSQL 16. The lab runs K3s 1.36.5.
[PostgreSQL's version policy](https://www.postgresql.org/support/versioning/)
listed 16.15 as the current stable PostgreSQL 16 minor when selected.
The operand image is pinned to `16.15-system-trixie` and its OCI index digest.

The [Barman Cloud Plugin requirements](https://cloudnative-pg.io/plugin-barman-cloud/docs/intro/)
include CNPG >=1.26 (>=1.27 recommended). This installation therefore supports
the subsequent plugin integration. The plugin, its TLS prerequisites, R2
credentials, ObjectStores, WAL archiving, backup schedules and retention are
not installed here. No backup or restoration readiness is implied.
