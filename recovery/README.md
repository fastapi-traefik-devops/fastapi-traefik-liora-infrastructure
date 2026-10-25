# Recovery inputs and validation

Keep real inputs in this Git-ignored directory. New files under `recovery/`
are ignored by default; tracked examples and validator source files are
exceptions. Set `.env`, `recovery.yaml`, SSH
private keys and optional cluster tokens mode `0600` (or more restrictive).
The public SSH key may be `0644`. Back up these files outside Git; the checker
only reads them. Tracked `.example` files intentionally contain unusable fake
credentials. Copy them, then replace every placeholder before use.

Prepare Python and the checkout-local environment using
[runbook 11](../runbooks/11-install-management-tools.md#operator-python-and-browser-tools).
Then validate from the repository root:

```sh
RECOVERY_PYTHON="$PWD/.local-work/venv/bin/python" bash recovery/check_credentials.sh --all --offline
```

The Bash entry point delegates to `check_credentials.py`; copy both files and
`requirements.txt` together if copying the checker to another server.
`RECOVERY_PYTHON` selects Python; `RECOVERY_DIR` selects the input directory
(default: the checker directory). These control variables do not belong in `.env`.
Neither input values nor exception text, PEM content, HTTP bodies or parser
snippets are printed. Diagnostics identify field names, YAML paths and unknown
key/variable line numbers. Do not invoke the checker with shell tracing enabled.

| Invocation/result | Behavior |
| --- | --- |
| `--all` (default) | Require all ten `.env` variables, SSH pair and complete YAML with all three application environments. |
| `--tailscale` | Require the seven Proxmox/storage/Tailscale variables and SSH pair. GHCR fields are optional but checked if supplied. YAML is optional; if present, require schema version and validate every supplied section completely. |
| `--offline` | Skip the live API read; this is informational, not a warning. No provider permissions, expiry or resource existence are verified. |
| Default online | After successful local validation, read Proxmox template 9013 on the selected node. Accept only HTTP 200; no mutation. The Proxmox self-signed TLS endpoint is accepted by this probe. Redirects are rejected so credentials are not forwarded. Tailscale/GHCR credentials are not authenticated by this check. |
| Exit `0` | No validation errors. Warnings are allowed by default. |
| Exit `1` | Validation/API failure, or any warning with `--strict-warnings`. |
| Exit `2` | Invalid options, missing runtime dependencies/interpreter, or an unexpected internal failure. |

Unknown and obsolete `.env` names and YAML keys produce warnings, including their
names and locations, without printing their values. They are never removed or
rewritten. Fix errors first; review warnings manually. `--strict-warnings` makes
warnings fatal for automated gates without changing their severity or deleting
anything. Recognized obsolete flat application variables (`SECRET_KEY`,
`FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_PASSWORD`, `SMTP_PASSWORD`)
belong under `application_credentials`; transient `TAILSCALE_AUTH_KEY` belongs
only in the provisioning shell, not the persistent recovery file. All other
unsupported names, including old Terraform input names, are also warned about.

## Display browser passwords

Run this helper from any directory with Python 3 and `kubectl` available:

```sh
python3 recovery/show_passwords.py
```

It explicitly warns that plaintext passwords will be printed and asks `y/n` on
standard error before reading any Secrets, then reads the answer from standard
input. This works in SSH sessions without requiring `/dev/tty` or an allocated
pseudo-terminal. Only `y` (case-insensitive) continues; any other answer or EOF
cancels. There is no flag to skip confirmation; piped input is read as an answer.
The helper performs read-only Kubernetes queries on every invocation and does
not create files, cache credentials, modify Secrets, or authenticate to services.
It prints a tab-separated table for PROD/STAGE/DEV, including Application,
Argo CD, Grafana, Prometheus, Alertmanager and Adminer, plus shared NONPROD Jenkins.
The service addresses describe the current Admin VIP deployment.

Defaults are `~/.kube/config-dev-stage` and `~/.kube/config-prod`; override them
with `--nonprod-kubeconfig PATH` and `--prod-kubeconfig PATH`. The operator needs
read access to the referenced ConfigMaps and Secrets. No Python packages beyond
the standard library are required; the single script can be copied to a server.

The table contains real plaintext credentials. Terminal scrollback, recording,
redirected output and pipes can retain them; do not put this output in Git.
Argo CD uses the initial-admin Secret, which may be stale after password rotation
or absent after deletion. Application and database passwords also reflect stored
Secrets, without verifying the actual login. Shared DEV/STAGE interfaces repeat
the same credentials. Prometheus and Alertmanager have no separate authentication.

Exit `0` means the table was printed or the operator cancelled; `1` means a
resource/field read failed; `2` means invalid arguments or unreadable standard input;
`130` means interruption. Failed collection prints no partial table; diagnostics
exclude kubectl response bodies and secret values.

## `.env`

Use one `NAME=value` or `export NAME=value` assignment per line. Blank lines and
comments are supported, as are literal single/double quotes, escapes, and `$NAME`
or `${NAME}` references to earlier assignments in this file. No process
environment fallback, shell commands, substitutions, multiline assignments,
`source`, or duplicate assignments are allowed. Single-quoted command-like text
is literal and is never executed. Quote spaces and secret punctuation. Unknown
variables still need valid assignment syntax. Do not store executable shell code
in this file: the checker parses it as data even though Terraform runbooks later
source it in the operator's trusted shell.

All text must be encodable as UTF-8. Supported variables are nonempty strings
without NUL or example/default
placeholders. Seven are required in both modes:

| Name | Actual format/constraint |
| --- | --- |
| `TF_VAR_pm_endpoint` | Absolute HTTPS origin: DNS host, IPv4 or bracketed IPv6; optional port 1–65535; optional trailing `/`. No userinfo, query, fragment, extra path, whitespace or control characters. |
| `TF_VAR_pm_node` | Proxmox node identifier: ASCII letters/digits/hyphens, starts and ends with a letter or digit. No invented fixed maximum. |
| `TF_VAR_pm_api_token` | `user@realm!tokenid=UUID`. User ID up to 64 characters; username excludes whitespace, `:` and `/`. Realm and token ID start with an ASCII letter and contain at least two letters/digits/`.`/`_`/`-` characters. Secret is a canonical hyphenated UUID. |
| `DISK_STORAGE` | Proxmox storage ID: at least two ASCII characters, starts with a letter, ends with a letter/digit; interior letters/digits/`.`/`_`/`-`. |
| `TF_VAR_cloud_init_datastore_id` | Same storage format, and must equal `DISK_STORAGE`; `"$DISK_STORAGE"` is supported. |
| `TAILSCALE_API_KEY` | Literal `tskey-api-` followed by a nonempty opaque letters/digits/`_`/`-` body. Auth keys and OAuth/client secrets are different inputs. No undocumented fixed token length is imposed. |
| `TAILSCALE_TAILNET` | Nonempty tailnet identifier using letters/digits/`.`/`_`/`@`/`-`, or `-` for the credential owner's tailnet. |

Three more are required by `--all`, and checked if present with `--tailscale`:

| Name | Actual format/constraint |
| --- | --- |
| `GHCR_REGISTRY` | Exactly `ghcr.io`, as required by the bootstrap consumer. |
| `GHCR_USERNAME` | GitHub username, 1–39 ASCII letters/digits/hyphens; no initial, final or consecutive hyphens. |
| `GHCR_TOKEN` | Personal access token (classic): `ghp_` plus 36 alphanumeric characters, or 40 hexadecimal characters. Grant `read:packages` and authorize organization access as needed. |

Optional `PROXMOX_PUBLIC_IP` is a dotted IPv4 address for the management SSH
procedure. Documentation-only addresses in `.example` are not real endpoints.

These checks follow the [Proxmox schema](https://github.com/proxmox/pve-common/blob/master/src/PVE/JSONSchema.pm),
[identity rules](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/Auth/Plugin.pm),
[token generation](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/TokenConfig.pm),
[Tailscale key types](https://tailscale.com/docs/reference/key-secret-management),
and [GHCR authentication requirements](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
Token shape does not establish validity, scopes or expiry.

## `recovery.yaml`

The version 1 document holds application credentials and database backup
inputs. With `--all`, the checker requires `application_credentials`.
Mappings use unique string keys. YAML anchors, aliases, merges, and custom
tags are unsupported. Unknown fields warn at every mapping level.

| Path | Constraint |
| --- | --- |
| `schema_version` | Integer `1` (a Boolean or quoted number is invalid). |
| `application_credentials` | Mapping containing `dev`, `stage`, `prod`; each has all fields below. |
| `application_credentials.<env>.namespace` | Exactly `app-dev`, `app-stage` or `app-prod`, matching `<env>`. |
| `…first_superuser` | Valid application `EmailStr`, at most 255 characters, with deliverability checks disabled. Must match the current ConfigMaps/bootstrap account `admin007@liora.aprt.info`. The tracked example intentionally uses a fake address that must be replaced. |
| `…backend-secrets.SECRET_KEY` | Nonempty string without NUL/default placeholders; fewer than 32 UTF-8 bytes warns. No invented 43-character requirement or hard maximum. Generate independent strong keys per environment. |
| `…backend-secrets.FIRST_SUPERUSER_PASSWORD` | 8–40 Python/Unicode characters, as required by application `UserCreate`; nonempty and no NUL/default placeholders. |
| `…backend-secrets.POSTGRES_PASSWORD` | Nonempty string without NUL/default placeholders; no arbitrary maximum or URL-safe-only restriction. |
| `…backend-secrets.SMTP_PASSWORD` | String without NUL; empty is explicitly supported when SMTP authentication is disabled. Nonempty example placeholders fail. |
| `…db-secrets.POSTGRES_PASSWORD` | Same constraint as the backend database password and must equal it within this environment. |

Application constraints come from `backend/app/models.py` (`UserBase`/`UserCreate`)
and `backend/app/core/config.py` in the application repository; consumer-specific
namespace/account requirements come from
[bootstrap-application-secrets.py](../scripts/kubernetes/bootstrap-application-secrets.py)
and [runbook 13](../runbooks/13-deploy-application-manifests.md).
A clean check does not rotate credentials or verify that live databases match them.

## SSH and optional K3s tokens

`LIORA-id_ed25519` must be a parseable unencrypted OpenSSH Ed25519 private key;
`LIORA-id_ed25519.pub` must be its matching OpenSSH public key. Encrypted keys
cannot be used by this unattended automation. Public-key comments are ignored.

If present, `k3s-dev-stage.token` and `k3s-prod.token` must contain the current
Ansible producer's 64 ASCII letters/digits, optionally followed by one newline.
These optional files are generated on first provisioning; absence is allowed in
both modes. Secure `K10…` tokens copied from a running K3s server are a different
format and must not replace these producer-managed raw token files.

## Verification

```sh
"$RECOVERY_PYTHON" recovery/test_check_credentials.py
```

Tests generate disposable keys and secret canaries in a system temporary
directory, then remove it. They exercise every required
field, formats/types/boundaries, strict warning exits, unknown-field preservation,
parser attacks and redaction on success and failure. API coverage uses mocks and
a disposable local HTTPS server, including redirect rejection; no live credentials
or infrastructure changes are needed.

## Jenkins GitHub App installation recovery

Preserve a complete stopped-controller home archive, mounted configuration,
image/plugin pins, administrator profile and credential encryption material in
the protected off-host recovery kit. Keep source archives immutable. Restore
under an execution hold and verify administrator access and credential decryption
before allowing jobs. Follow the [Jenkins state checklist](../runbooks/17-migrate-jenkins-ci.md#6-controller-backup-and-recovery-checklist).

The fresh foundation overlay creates a new home. An accepted controller must
retain its selected PVC and matching configuration. Use
[the controller restore runbook](../runbooks/23-restore-jenkins-controller.md)
before starting a restored controller.

Restoring a GitHub App key does not restore its repository selection or granted
permissions. Recover the existing `fastapi-gitops` installation with access to
both the application and infrastructure repositories, **Contents: Read and write**,
**Pull requests: Read and write**, and **Metadata: Read-only**. Keep the CI App
application-only with contents/PR read and commit-status write. Follow the
[GitHub App setup and verification procedure](../runbooks/17-migrate-jenkins-ci.md#2-configure-delivery-identities)
and verify actual installation grants before
resuming promotion; never place App private keys or installation tokens in Git.

## CloudNativePG database bootstrap

The current environment manifests use `POSTGRES_SERVER=db`, database `app`
and application owner `app_owner`. CNPG bootstrap Secret `cnpg-app` contains
that username and the existing environment database password; `cnpg-superuser`
contains administrative username `postgres` and the same existing password.
`backend-secrets` and `db-secrets` values and the recovery YAML schema are
unchanged. Recreate the two derived Secrets using
[bootstrap-cnpg-secrets.py](../scripts/kubernetes/bootstrap-cnpg-secrets.py)
after restoring the original application Secrets. Never track their values.

Adminer retains `server=db`, database `app`, administrative user `postgres`.
The password-table helper reads `cnpg-superuser` for CNPG environments rather
than requiring the retired `db-config`. Existing application administrator
credentials are reapplied only when initializing an empty database, not when
restoring an existing account. See [runbook 18](../runbooks/18-cloudnative-pg.md).

Fresh CNPG installation initializes empty data. Existing application rows and
schema recover from R2 physical backups plus WAL using the selected recovery
point; private recovery inputs alone are not a database backup. See the
[recovery navigator](../01-Disaster_recovery.md) and [backup operations](../runbooks/19-cnpg-r2-backup-pitr.md).

## Database physical-backup R2 inputs

Optional root `database_backups` is fully validated when present (same warning
and exit-code rules as other fields). Required keys: `account_id` (32 hex),
`endpoint` (HTTPS S3 account/jurisdiction endpoint, no path), `jurisdiction`
(`default`, `eu`, `fedramp`), `region` (`auto`), `bucket` (`liora-backup`),
`access_key_id` (32 hex), `secret_access_key` (64 hex). Optional `api_token`
is a nonempty opaque Cloudflare API credential; no invented fixed token length.
Only the S3 pair is installed in application namespaces. The API token is kept
for owner-operated metadata checks; do not broaden permissions on a denied read.

Use one pair scoped to the private dedicated bucket. Environment prefixes do
not isolate credentials. No secret value belongs in Git or logs; examples are
visibly fake. The interactive password helper includes this R2 pair and optional
API token only after its existing explicit plaintext-output confirmation.
Private recovery inputs are not database backups. See
[runbook 19](../runbooks/19-cnpg-r2-backup-pitr.md).

The optional generated `backup-coordinator.json` is ignored and mode 0600.
Its supported fields are shown by the deliberately fake `.json.example`.
The checker validates version 1, the fixed VM 250 listener/state directory,
R2 equality with YAML inputs, exact NONPROD/PROD API and Alertmanager addresses,
parseable public CA certificates and coordinator service-account JWT subjects
(and expiry when present). Unknown keys warn with locations, never values.
The API verifies token signatures and namespace RBAC. This file grants no
application/Secret/Pod/PVC writes; preserve it in the private recovery kit.
The token Secrets are persistent purpose-scoped service-account credentials;
rotate/reprovision them if compromised. Never substitute administrator kubeconfigs.
Generate with `scripts/backups/provision.py`; do not hand-copy example tokens.

## Public certificate DNS API input

Public certificate management uses a separate private file,
`recovery/cloudflare-dns-token` (mode `0600`), containing only the Cloudflare DNS
API token. It is Git-ignored. The adjacent `.example` contains a visibly fake
placeholder. Do not use the R2 bucket credentials for DNS.

Required scope: `Zone:DNS:Edit` and `Zone:Zone:Read` for `aprt.info`. Preserve
this file in the encrypted recovery kit. Validate it with
`python3 scripts/kubernetes/bootstrap-cloudflare-dns.py`; this is separate from
the YAML/environment schema checked by `check_credentials.sh`.

See [certificate preparation and activation](../kubernetes/platform/public-certificates/README.md).
Use [runbook 15](../runbooks/15-publish-application.md) to reissue certificates
after rebuilding clusters.

## Recovery kit checklist

- [ ] Preserve `.env`, `recovery.yaml`, SSH identity, current K3s tokens and the DNS API token outside Git.
- [ ] Preserve Grafana/Jenkins private platform records, GitHub App IDs/keys and Slack channel-bound webhooks separately from Git configuration.
- [ ] Preserve infrastructure module state and provider settings; match them to the intended repository revision.
- [ ] Preserve Jenkins home/encryption material as a complete controller archive; database backups do not include it.
- [ ] Preserve generated coordinator access and its source configuration; after cluster replacement review CA/token changes before regenerating its access profile.
- [ ] Match every database recovery point to the environment archive and credentials applicable at that point.
- [ ] Keep original archived key/state copies while preparing working recovery copies.

## Private operator data

`.local-work/` is Git-ignored but is not uniformly disposable. Classify contents
before cleanup or moving the checkout:

| Data | Handling |
| --- | --- |
| `venv/`, `browsers/`, downloaded validation tools and build/render caches | Recreate from the pinned setup in runbook 11. |
| `private/platform/` Grafana/Jenkins credential records | Preserve off-host with mode-0600 files and mode-0700 parent directories. |
| Registry client authentication and generated Secret manifests | Protect as credentials; preserve required inputs in the encrypted recovery kit. |
| Jenkins home archives, keys, private configuration and transfer receipts | Preserve together with matching image/plugin/configuration metadata. |
| Coordinator access profiles and retained cycle journals | Preserve private access/state; reconcile cluster CA/token identities after rebuild. |
| Module Terraform state and private deployment inputs | Preserve per module; never overwrite originals during state reconciliation. |
| Incident/change output with private diagnostics or authentication metadata | Review and protect before sharing or cleanup; retain required recovery evidence off-host. |

- [ ] Inventory ignored files before removing a checkout or cleaning generated directories.
- [ ] Copy required private data into the protected off-host recovery kit and verify its integrity before deleting a local copy.
- [ ] Keep SSH identities and kubeconfigs in protected locations; do not put them into VM templates or ordinary source artifacts.
- [ ] Keep browser sessions, traces, raw Secret responses and password-helper output out of public evidence.
- [ ] Publish only sanitized results under `docs/testreports/`.


## K3s server tokens and recovery identities

| Cluster | Current original server token |
| --- | --- |
| NONPROD | `recovery/k3s-nonprod-server.token` |
| PROD | `recovery/k3s-prod-server.token` |

These files contain the actual secure token copied from
`/var/lib/rancher/k3s/server/token`. They are Git-ignored, mode `0600`.
Do not generate replacements to fill these files. The kubeconfig-fetch play saves
the actual token during fresh setup and refuses to overwrite a different token.
The recovery checker validates supplied secure-token files without printing them;
absence is allowed before initial cluster creation.

These tokens differ from optional Ansible provisioning files
`k3s-dev-stage.token` / `k3s-prod.token`. Keep both contracts separate; do not put a
secure `K10…` token into a raw provisioning-token file. The tracked `.example`
files are visibly fake and cannot replace a captured token.

Keep node passwords, cluster UID, K3s version and token checksum in private
`recovery/k3s-identities/<cluster>-<capture-id>/` metadata directories. Capture
identities **without snapshots**:

```sh
cluster=nonprod
capture_id=$(date -u +%Y%m%dT%H%M%SZ)
python3 scripts/recovery/export-k3s-recovery.py --cluster "$cluster" \
  --known-hosts "$HOME/.ssh/known_hosts" --identities-only \
  --output "$PWD/recovery/k3s-identities/$cluster-$capture_id"
```

Standalone tool: [export-k3s-recovery.py](../scripts/recovery/export-k3s-recovery.py).

Repeat for PROD. Use the actual verified SSH host-key file. An existing matching
fixed token is reused; a differing token is not overwritten. Directory modes are
`0700`; file modes are `0600`. Tokens are not duplicated in metadata directories.

Use your existing `recovery/make_recovery_backup.sh` workflow to create the
encrypted archive, then keep a copy outside the host. It includes untracked
fixed token files and identity metadata automatically. The archive password is
entered through its terminal prompt; this setup adds no password file or new
off-host destination. Keep the password separate from the archive.

Before rotating a token, retain its current file under a dated historical name.
After the remote token has been rotated, capture its new actual value at the
fixed path. Keep the previous token and matching metadata while any retained
snapshot needs it. For example, preserve NONPROD's old file before recapture:

```sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
mv recovery/k3s-nonprod-server.token "recovery/k3s-nonprod-server.previous-$stamp.token"
```

Capture metadata into a new directory after token rotation or K3s upgrade. Update
the encrypted archive. This capture procedure does not rotate a cluster token.

Do **not** store etcd snapshot files in `recovery/`. Local snapshots stay on K3s
nodes; native K3s uploads directly to `liora-backup/etcd/nonprod/` and
`liora-backup/etcd/prod/`. Temporary download/check or manual restore work belongs
in a private `.local-work/` directory. It is not part of the credentials archive.
The download/export tools reject snapshot destinations inside `recovery/`.

Native S3 configuration reuses the existing `database_backups` endpoint, region
and bucket-scoped pair. No new YAML fields are needed. Prefixes separate data,
not credential access. Keep the bucket private.

[Etcd operations](../docs/operations/ETCD_BACKUPS.md) covers scheduling and checks.
[Runbook 21](../runbooks/21-restore-k3s-etcd-snapshot.md) is the optional manual
restore route. Its `--token-file` option selects a historical token when required.
Routine verification does not copy a token per snapshot. Metadata/checksum checks
do not prove restoration or bootstrap-data decryption. Etcd never backs up PVC
file contents.

## Live PostgreSQL recovery selections

Keep generated bundles and incident selections under ignored
`recovery/live-restore/`, mode `0700`, with files `0600`. Follow
[runbook 20](../runbooks/20-restore-live-postgresql.md). Record the environment,
physical backup ID, timezone-qualified target, application image pair, source
archive and the new post-recovery destination/server identity. Recover the
matching credentials from the protected kit; never substitute empty database
initialization. Do not include credentials in GitOps recovery resources or patches.
