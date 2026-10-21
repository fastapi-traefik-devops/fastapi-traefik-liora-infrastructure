# Preserved application platform sources

These are provenance/reference inputs, not an installation entrypoint. Do not
apply their kind-specific manifests or run their bootstrap scripts on K3s.
Active cluster configuration lives in `../nonprod/`, `../prod/`, and `../base/`.

Source: `fastapi-traefik-devops/fastapi-traefik-liora-application`, commit
`b98a22e48527c256193ed65c10307eb574b27ab6` (clean source checkout).
Selected paths: `monitoring/` and `infra/jenkins-host/`.

Selected history was exported with Git fast-export and imported with fast-import
under `kubernetes/platform/upstream/`, then merged without squashing or rebasing.
The import retains 22 commits, original authors, dates and messages; rewritten
object IDs reflect the restricted tree and new paths. Original application and
infrastructure histories remain unchanged. No additional working checkout was
created. Import tip: `859a076cd30e19b242c2653d97826d1fd05fd9af`.

Gitleaks reviewed 19 nonempty selected commits before import. Its 27 generic-key
findings were exclusively public Jenkins plugin versions in `plugins.lock.txt`
at source commits `25f7aea9b20d` and `4916cf8a6ab7`. Every flagged ID/version was
resolved against its public `updates.jenkins.io/download/plugins/` artifact.
A second scan with only that file's generic-key findings excluded passed.
Other rules and files remained enabled. Private scan/export evidence is kept
under the ignored `.local-work/phase8/` directory.

Retain the source Dockerfiles, plugin/tool/image locks, JCasC and Job DSL for
staged adaptation. Phase 8 loads a separate minimal controller-only JCasC;
source jobs, agents, publisher credentials and schedules are not activated.
Monitoring adaptations replace kind storage/labels and provide cluster-specific
endpoints, dashboards and rules. External alert delivery stays disabled until
the operator agrees its destination.
