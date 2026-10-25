# Archived application infrastructure procedures

Historical source: application repository commit
`2a6e05a91489b2d9475e25157ab73d8ff9c98d08`, archived 2026-10-25.

These files preserve old kind/Docker-host deployment decisions, procedures
and observations during repository cleanup. They are not installation
entrypoints. Relative links and commands retain their original source context.
Use current infrastructure runbooks for operations.

Host image Dockerfiles, build scripts and tool locks were compared byte for
byte with `kubernetes/platform/upstream/infra/jenkins-host/`; they match.
The differing README, SECURITY, Job DSL and GitHub App diagnostic script
are retained here. The former CI image-audit helper is also preserved for
reference; it is not wired into current operations. Do not execute the archived Job DSL. Other retired source
remains available in application Git history at the commit above.

This archive supplements Phase 8 and Phase 9 reports. It does not replace
Jenkins state backups, private recovery inputs or operational runbooks.
