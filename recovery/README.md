# Recovery inputs and validation

Keep real inputs in this Git-ignored directory, with `.env`, `recovery.yaml`, SSH
private keys and optional cluster tokens mode `0600` (or more restrictive).
The public SSH key may be `0644`. Back up these files outside Git; the checker
only reads them. Tracked `.example` files intentionally contain unusable fake
credentials. Copy them, then replace every placeholder before use.

Install Python 3 and the validator dependencies in an operator-owned environment:

```sh
python3 -m venv "$HOME/liora-recovery-tools"
"$HOME/liora-recovery-tools/bin/pip" install -r recovery/requirements.txt
export RECOVERY_PYTHON="$HOME/liora-recovery-tools/bin/python"
bash recovery/check_credentials.sh --all --offline
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
| Default online | After successful local validation, read Proxmox template 9013 on the selected node. Accept only HTTP 200; no mutation. Lab self-signed TLS is accepted, as in the previous checker. Redirects are rejected so credentials are not forwarded. Tailscale/GHCR credentials are not authenticated by this check. |
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
| `TAILSCALE_TAILNET` | Nonempty tailnet identifier using letters/digits/`.`/`_`/`@`/`-`, or `-` for the credential owner's tailnet. Opaque and legacy identifiers are supported. |

Three more are required by `--all`, and checked if present with `--tailscale`:

| Name | Actual format/constraint |
| --- | --- |
| `GHCR_REGISTRY` | Exactly `ghcr.io`, as required by the bootstrap consumer. |
| `GHCR_USERNAME` | GitHub username, 1–39 ASCII letters/digits/hyphens; no initial, final or consecutive hyphens. |
| `GHCR_TOKEN` | Personal access token (classic): `ghp_` plus 36 alphanumeric characters, or legacy 40 hexadecimal characters. Fine-grained PATs and GitHub App tokens are outside this persistent schema. The operator must grant `read:packages` and authorize organization access as needed. |

Optional `PROXMOX_PUBLIC_IP` is a dotted IPv4 address for the management SSH
procedure. Documentation-only addresses in `.example` are not real endpoints.

These checks follow the [Proxmox schema](https://github.com/proxmox/pve-common/blob/master/src/PVE/JSONSchema.pm),
[identity rules](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/Auth/Plugin.pm),
[token generation](https://github.com/proxmox/pve-access-control/blob/master/src/PVE/TokenConfig.pm),
[Tailscale key types](https://tailscale.com/docs/reference/key-secret-management),
and [GHCR authentication requirements](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
Token shape does not establish validity, scopes or expiry.

## `recovery.yaml`

The complete version 1 document has exactly these supported paths. Every listed
field is required by `--all`. Mappings use unique string keys; YAML anchors,
aliases, merges and custom tags are unsupported. Unknown fields warn at every
mapping level, including controller list items, Secret key maps and nested keys
inside unsupported sections.

| Path | Constraint |
| --- | --- |
| `schema_version` | Integer `1` (a Boolean or quoted number is invalid). |
| `kubernetes.nonprod.sealed_secrets_controller_keys` | Nonempty list of controller key records. This is the currently supported nonproduction controller backup; no `prod` controller key section is consumed today. |
| `…[i].secret_name` | Unique original Kubernetes Secret DNS subdomain name, at most 253 characters: lowercase letters/digits/`-`/`.` with each component starting and ending with a letter/digit. |
| `…[i].tls_crt_pem` | Parseable PEM X.509 certificate whose public key matches the private key below. |
| `…[i].tls_key_pem` | Parseable, unencrypted RSA PEM private key (PKCS#1 or PKCS#8), required by Sealed Secrets RSA encryption. Keys shorter than 2048 bits warn. |
| `application_credentials` | Mapping containing `dev`, `stage`, `prod`; each has all fields below. |
| `application_credentials.<env>.namespace` | Exactly `app-dev`, `app-stage` or `app-prod`, matching `<env>`. |
| `…first_superuser` | Valid application `EmailStr`, at most 255 characters, with deliverability checks disabled. Must match the current ConfigMaps/bootstrap account `admin007@liora.aprt.info`. The tracked example intentionally uses a fake address that must be replaced. |
| `…backend-secrets.SECRET_KEY` | Nonempty string without NUL/default placeholders; fewer than 32 UTF-8 bytes warns. No invented 43-character requirement or hard maximum. Generate independent strong keys per environment. |
| `…backend-secrets.FIRST_SUPERUSER_PASSWORD` | 8–40 Python/Unicode characters, as required by application `UserCreate`; nonempty and no NUL/default placeholders. |
| `…backend-secrets.POSTGRES_PASSWORD` | Nonempty string without NUL/default placeholders; no arbitrary maximum or URL-safe-only restriction. |
| `…backend-secrets.SMTP_PASSWORD` | String without NUL; empty is explicitly supported when SMTP authentication is disabled. Nonempty example placeholders fail. |
| `…db-secrets.POSTGRES_PASSWORD` | Same constraint as the backend database password and must equal it within this environment. |

Expired/not-yet-valid controller certificates warn rather than fail: historical
private keys can still be needed to decrypt backups. Retain all required original
key pairs; do not generate replacements for old encrypted SealedSecrets. Name
rules follow [Kubernetes resource names](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/).
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

Tests generate disposable SSH/controller keys and secret canaries in a temporary
directory under the operator's home, then remove it. They exercise every required
field, formats/types/boundaries, strict warning exits, unknown-field preservation,
parser attacks and redaction on success and failure. API coverage uses mocks and
a disposable local HTTPS server, including redirect rejection; no live credentials
or infrastructure changes are needed.

## Jenkins GitHub App installation recovery

Jenkins Phase 9 state is restored under a hold. Retain both private source and
foundation backups, the staged home, current-admin XML and transfer/acceptance
receipts under `.local-work/private/phase9/` in protected operator recovery storage;
they include credential-bearing data and must never enter Git. The current K3s
admin login is authoritative; the legacy admin profile remains in source backup
only. Follow the [state transfer and retained-PVC rollback procedure](../runbooks/17-migrate-jenkins-ci.md#restore-to-a-new-pvc-while-retaining-the-current-admin-login).
Fresh bootstrap uses the default Jenkins overlay; an existing restored controller
uses `kubernetes/platform/nonprod/jenkins/held`. Do not apply the foundation over
that controller or activate old jobs/promotion as part of credential recovery.

Restoring a GitHub App key does not restore its repository selection or granted
permissions. Recover the existing `fastapi-gitops` installation with access to
both the application and infrastructure repositories, **Contents: Read and write**,
**Pull requests: Read and write**, and **Metadata: Read-only**. Keep the CI App
application-only with contents/PR read and commit-status write. Follow the
[GitHub App setup and verification procedure](../runbooks/17-migrate-jenkins-ci.md#configure-or-recover-the-fastapi-gitops-github-app)
and its standalone read-only checker. Verify actual installation grants before
resuming promotion; never place App private keys or installation tokens in Git.
