# Application deployment source and history

Source: `https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application`.
Source HEAD: `b98a22e48527c256193ed65c10307eb574b27ab6`.
The read-only local checkout was initially reviewed at
`1a5b24f096dd1a6234fa101f8648e40db88b52c7`; a read-only upstream check
identified the newer STAGE promotion, which was imported with its history too.

Only `deploy/base/` and `deploy/overlays/{dev,stage,prod}/` were selected.
A disposable clone was filtered using git-filter-repo 2.47.0, merged with
unrelated histories on the isolated migration branch, then moved using Git
renames into this directory. The application checkout was not modified.
Neither application code nor historical `k8s/`, Argo CD, monitoring, or Jenkins
files were imported. Both promotion JSON files are retained as historical
records; Kustomize does not consume them.

## Credential review and preservation checks

Before the import, all 25 unique selected historical blobs were scanned in
six change snapshots (110 file instances) with Gitleaks 8.30.1 default rules,
explicitly ignoring source allow comments and without source ignore files.
There were no findings and no Secret or SealedSecret resources. The official
Gitleaks release checksum was checked before execution. The filtered eight-commit
history was also scanned with no findings. A scanner result is not proof that
arbitrary secrets can never be present; no live credentials were imported.

The filter retained six change commits and two merge commits. Every retained
commit's author and committer identity, timestamp, message, and selected tree
were compared with the original. All selected blob IDs are identical, and all
eight commits' blobs were covered by the pre-import scan. Commit hashes changed
because the parent histories and trees changed. The original-to-imported map
is in [SOURCE_HISTORY.tsv](../../kubernetes/apps/liora/SOURCE_HISTORY.tsv).

Historical paths are still `deploy/...` in the imported parent history.
After the Git move, inspect history with, for example:

```sh
git log --follow -- kubernetes/apps/liora/overlays/stage/kustomization.yaml
git log --follow -- kubernetes/apps/liora/base/deployment-db.yaml
git show 7ba472d1094d233da73c4be5ce2ab9f9f6f5347e:deploy/overlays/stage/kustomization.yaml
```

The last command demonstrates the imported single-worker change. History
comparison and source-tree equality were checked before environment-specific
edits. Subsequent local commits intentionally adapt domains and initial
administrator identity; image changes require explicit release selection.

## Scope and validation

This is a manual deployment baseline. PostgreSQL, its PVC, Adminer, prestart,
resource requests, probes, replicas, and Argo annotations remain in place.
See [the deployment runbook](../../runbooks/13-deploy-application-manifests.md)
for the later application order and acceptance checks. Import and local render
validation do not establish that anything has been deployed on K3s.
