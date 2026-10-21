# Local operator workspace

Work from the main `fastapi-traefik-liora-infrastructure` checkout. Scripts,
runbooks, manifests and reports are maintained here; additional migration
checkouts and home-directory tool environments are no longer needed.

`.local-work/` is ignored by Git. It holds machine-specific tools and generated
output, and must be included separately in an operator backup when needed:

| Path | Purpose |
| --- | --- |
| `.local-work/venv/` | Python dependencies for recovery and browser checks |
| `.local-work/browsers/` | Playwright browser downloads |
| `.local-work/browser-deps/root/` | Optional extracted Chromium libraries for this lab |
| `.local-work/tools/` | Local Gitleaks executable and scan configuration |
| `.local-work/render/<environment>/` | Newly rendered application manifests |
| `.local-work/acceptance/<environment>/` | New acceptance records |

## Prepare another operator machine

From the checkout root, with Python 3.12 and venv support available:

```sh
mkdir -p .local-work
chmod 700 .local-work
python3 -m venv .local-work/venv
.local-work/venv/bin/python -m pip install -r scripts/requirements-local-tools.txt
bash scripts/local-python.sh -m playwright install --with-deps chromium
```

Installing Chromium system libraries requires package-management privileges.
On this lab host, the existing extracted libraries were moved into
`.local-work/browser-deps/root/`; the wrapper adds those libraries to the
browser environment automatically. Other machines should install their own
system dependencies. Python environments and native libraries are specific
to their machine; recreate the environment after moving a checkout to a new
location or machine.

Use the wrapper instead of a home-directory Python path:

```sh
bash scripts/local-python.sh scripts/kubernetes/verify-application-ui.py
RECOVERY_PYTHON="$PWD/.local-work/venv/bin/python" \
  bash recovery/check_credentials.sh --all --offline --strict-warnings
.local-work/tools/gitleaks dir scripts --config .local-work/tools/scan.toml --redact --no-banner
```

The browser helper needs the environment selection, recovery directory and
acceptance path from the relevant runbook. It performs real application writes;
run it only as part of an authorized acceptance procedure. Gitleaks is a
separately installed executable (currently 8.30.1), not a Python dependency.
For targeted scans, pass the reviewed source path rather than generated
operator data. Review and back up ignored data before deleting any checkout.

## Existing evidence and deployed files

Completed-phase artifacts remain archived under
`~/_DEL-me/migration-artifacts-20261021T181827Z/`. Its `manifest.json` maps the
original paths quoted in historical reports to their archive locations and
records verified hashes and metadata. Those artifacts are retained evidence,
not required working copies. Keep reports and plans in `docs/testreports/`.

Recovery inputs and SSH identity remain in ignored `recovery/` files; SSH
configuration and kubeconfigs remain in their standard home locations.
Terraform state and certificate-sync service files on management VM 200
remain at `~/liora-phase7-edge/`. These are deployed runtime files and are
maintained from the source in this repository. Relocating a running service
or its state requires its own reviewed procedure.
