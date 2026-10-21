# Local workspace consolidation — 2026-10-21

The original infrastructure checkout now holds all active local operator tools
under ignored `.local-work/`, mode `0700`. There is no separate migration
worktree. Application source remains in its original read-only repository.

| Original local location | Location inside the checkout |
| --- | --- |
| `~/liora-migration-tools/` | `.local-work/venv/` |
| `~/liora-browser-deps/` | `.local-work/browser-deps/` |
| `~/liora-history-review/` (remaining scanner/configuration) | `.local-work/tools/` |
| `~/.cache/ms-playwright/` | `.local-work/browsers/` |

The directories were moved without copies or compatibility symlinks. Python
launcher and activation paths were repaired; installed package versions were
unchanged. Playwright registered the relocated browser installation. Local
move details are in ignored `.local-work/relocation.json`.

The browser wrapper resolves this checkout's tools and library paths.
Runbooks 13–15 now use it, and new render/acceptance output goes into
`.local-work/render/` and `.local-work/acceptance/`. Dependency versions and
recreation instructions are tracked in the repository.

## Validation

- Shell syntax and Git whitespace checks passed.
- Python dependency consistency passed; Playwright and git-filter-repo
  entry points worked at their new paths.
- Chromium launched and rendered a synthetic local page through the wrapper.
- Complete offline recovery validation with strict warnings returned zero
  errors and zero warnings. Live provider permissions/expiry were not tested.
- Gitleaks 8.30.1 scanned operator scripts with no leaks found.
- Git ignores the entire local workspace and existing recovery inputs.

No cluster, deployed service, Terraform state or credential was changed.
Existing untracked `kubernetes/StartPrompt.md` and
`kubernetes/IMPLEMENTATION_PLAN.md` were preserved. Historical evidence remains
in the private `_DEL-me` archive described in the
[workspace guide](../LOCAL_WORKSPACE.md); historical reports retain their
original evidence paths. The management VM's live `~/liora-phase7-edge/`
runtime is separate from local working artifacts and was not relocated.
