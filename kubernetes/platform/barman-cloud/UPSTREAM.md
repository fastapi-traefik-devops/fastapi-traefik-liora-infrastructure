# barman-cloud provenance

Unchanged official release asset `barman-cloud-0.15.1.yaml`, SHA-256 `8f377ff4a7d0d3f74fc64b0f7ac4f449fc38ca9e83a40107cca2f9315a9bd920`.

Source: https://github.com/cloudnative-pg/plugin-barman-cloud/releases/tag/v0.15.1
Requirements and installation: https://cloudnative-pg.io/plugin-barman-cloud/docs/installation/
Compatible with existing CNPG 1.30.1. Install in cnpg-system, including only
its internal self-signed TLS resources. The injected sidecar image is pinned
as well as the plugin controller.

Kustomize pins OCI digests and bounds controller resources.
