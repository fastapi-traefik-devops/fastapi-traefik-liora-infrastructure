# cert-manager provenance

Unchanged official release asset `cert-manager-1.21.2.yaml`, SHA-256 `e03b668ec8675214af6b0a671699d088f2601fa3878e0dbe1b41d3feafd1879f`.

Source: https://github.com/cert-manager/cert-manager/releases/tag/v1.21.2
Supported Kubernetes 1.36: https://cert-manager.io/docs/releases/
Only internal self-signed Certificate controllers are enabled; no application
ACME or ingress-shim controller. Public certificate migration remains Phase 11.

Kustomize pins OCI digests and bounds controller resources.
