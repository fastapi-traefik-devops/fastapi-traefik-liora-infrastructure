# Argo CD installation provenance

Argo CD v3.5.6 (released 2026-10-20), official multi-tenant installation:
https://github.com/argoproj/argo-cd/releases/tag/v3.5.6

Pinned upstream commit: `c2b1e3017e2cec86b122172e861dcd026453ae44`.
Official install manifest SHA-256:
`846c644bc81ce5557dd9048757a9c7353378f25c5eb811c77d32a9e907823599`.

Local patches set modest requests and memory limits for this lab. CPU limits
are omitted to allow startup on the slow shared host. All Services remain
ClusterIP, with no Ingress or external access configured. Two independent
installations use their local Kubernetes API, Redis and Argo CD Secrets.

Reference: https://argo-cd.readthedocs.io/en/stable/getting_started/
