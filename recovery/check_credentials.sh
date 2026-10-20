#!/usr/bin/env bash
# Check local recovery inputs without printing their values.
set -uo pipefail

recovery_dir="${RECOVERY_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
mode=--all
offline=false
for option in "$@"; do
  case "$option" in
    --all|--tailscale) mode="$option" ;;
    --offline) offline=true ;;
    *) printf 'Usage: %s [--all|--tailscale] [--offline]\n' "$0" >&2; exit 2 ;;
  esac
done

errors=0
warnings=0
error() { printf 'ERROR: %s\n' "$*" >&2; ((errors+=1)); }
warn() { printf 'WARN: %s\n' "$*" >&2; ((warnings+=1)); }
ok() { printf 'OK: %s\n' "$*"; }

check_private_mode() {
  local path="$1" label="$2" perms
  perms="$(stat -c '%a' -- "$path")" || { error "Cannot inspect $label permissions."; return; }
  if (( (8#$perms & 077) != 0 )); then
    error "$label is accessible to group or others; run: chmod 600 $path"
  else
    ok "$label permissions"
  fi
}

is_placeholder() {
  local value="$1"
  [[ "$value" == *'...'* || "$value" == REPLACE* || "$value" == CHANGE_ME* || "$value" =~ ^[AX]{8,}$ ]]
}

check_env_value() {
  local name="$1" value="${!1:-}"
  if [[ -z "$value" ]]; then
    error "$name is missing or empty in recovery/.env. Copy its entry from recovery/.env.example and fill it."
  elif is_placeholder "$value"; then
    error "$name still contains an example value in recovery/.env."
  else
    ok "$name is set"
  fi
}

check_proxmox_api() {
  local url status
  if [[ "$offline" == true ]]; then
    warn 'Skipped the live Proxmox API test (--offline).'
    return
  fi
  if ! command -v curl >/dev/null 2>&1; then
    error 'curl is required for the live Proxmox API test; install it or use --offline.'
    return
  fi
  url="${TF_VAR_pm_endpoint%/}/api2/json/nodes/${TF_VAR_pm_node}/qemu/9013/config"
  if status="$(printf 'Authorization: PVEAPIToken=%s\n' "$TF_VAR_pm_api_token" | \
      curl -q --header @- --insecure --silent --show-error --connect-timeout 5 --max-time 15 \
      --output /dev/null --write-out '%{http_code}' "$url" 2>/dev/null)"; then
    case "$status" in
      200) ok 'Proxmox API token can read template 9013 (HTTP 200)' ;;
      401) error 'Proxmox API rejected the token (HTTP 401).' ;;
      403) error 'Proxmox API token lacks permission to read template 9013 (HTTP 403).' ;;
      404) error 'Proxmox node or template 9013 was not found or is hidden (HTTP 404).' ;;
      *) error "Proxmox API template read returned HTTP $status." ;;
    esac
  else
    error 'Could not reach the Proxmox API; check its endpoint and run from VM 200, or use --offline.'
  fi
}

env_file="$recovery_dir/.env"
if [[ ! -f "$env_file" ]]; then
  error "Missing recovery/.env; copy recovery/.env.example and fill the values."
elif [[ ! -s "$env_file" ]]; then
  error "recovery/.env is empty."
elif ! bash -n "$env_file"; then
  error "recovery/.env has invalid Bash syntax."
else
  check_private_mode "$env_file" 'recovery/.env'
  # The local file is trusted operator input. Never enable shell tracing here.
  if ! source "$env_file"; then
    error "Could not load recovery/.env."
  else
    check_env_value TAILSCALE_API_KEY
    check_env_value TAILSCALE_TAILNET
    check_env_value TF_VAR_pm_endpoint
    check_env_value TF_VAR_pm_node
    check_env_value TF_VAR_pm_api_token
    if [[ -n "${TF_VAR_pm_endpoint:-}" && "${TF_VAR_pm_endpoint:-}" != https://* ]]; then
      error 'TF_VAR_pm_endpoint must start with https://.'
    fi
    if [[ -n "${TF_VAR_pm_api_token:-}" ]] && ! is_placeholder "${TF_VAR_pm_api_token:-}" && [[ ! "${TF_VAR_pm_api_token:-}" == *'@'*'!'*'='* ]]; then
      error 'TF_VAR_pm_api_token must have user@realm!tokenid=secret form.'
    fi
    if [[ -n "${TF_VAR_pm_endpoint:-}" && "${TF_VAR_pm_endpoint:-}" == https://* &&
          -n "${TF_VAR_pm_node:-}" && -n "${TF_VAR_pm_api_token:-}" ]] &&
       ! is_placeholder "${TF_VAR_pm_node}" &&
       ! is_placeholder "${TF_VAR_pm_api_token}" &&
       [[ "${TF_VAR_pm_api_token}" == *'@'*'!'*'='* ]]; then
      check_proxmox_api
    fi
    if [[ "$mode" == --all ]]; then
      check_env_value GHCR_REGISTRY
      check_env_value GHCR_USERNAME
      check_env_value GHCR_TOKEN
    fi
  fi
fi

private_key="$recovery_dir/LIORA-id_ed25519"
public_key="$recovery_dir/LIORA-id_ed25519.pub"
if [[ ! -s "$private_key" ]]; then
  error 'Missing recovery/LIORA-id_ed25519; restore the private key from the encrypted archive or generate the pair for a new installation.'
else
  check_private_mode "$private_key" 'SSH private key'
fi
if [[ ! -s "$public_key" ]]; then
  error 'Missing recovery/LIORA-id_ed25519.pub; restore the matching public key or derive it with ssh-keygen -y -f recovery/LIORA-id_ed25519.'
elif ! ssh-keygen -lf "$public_key" >/dev/null 2>&1; then
  error 'The SSH public key is not valid.'
fi
if [[ -s "$private_key" && -s "$public_key" ]]; then
  derived="$(ssh-keygen -y -P '' -f "$private_key" 2>/dev/null | awk 'NR == 1 {print $1, $2}')"
  declared="$(awk 'NR == 1 {print $1, $2}' "$public_key")"
  if [[ -z "$derived" ]]; then
    error 'The SSH private key could not be read non-interactively; unlock or replace it before automation.'
  elif [[ "$derived" != "$declared" ]]; then
    error 'The SSH public and private keys do not match.'
  else
    ok 'SSH key pair matches'
  fi
fi

if [[ "$mode" == --all ]]; then
  yaml_file="$recovery_dir/recovery.yaml"
  if [[ ! -s "$yaml_file" ]]; then
    error 'Missing recovery/recovery.yaml; restore it from the encrypted archive or copy recovery/recovery.yaml.example and fill it.'
  else
    check_private_mode "$yaml_file" 'recovery/recovery.yaml'
    if python3 - "$yaml_file" <<'PY'
import sys
try:
    import yaml
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
except ImportError:
    sys.exit(2)
try:
    with open(sys.argv[1], encoding='utf-8') as stream:
        data = yaml.safe_load(stream)
    entries = data['kubernetes']['nonprod']['sealed_secrets_controller_keys']
    if data.get('schema_version') != 1 or not isinstance(entries, list) or not entries:
        sys.exit(1)
    for item in entries:
        if not isinstance(item.get('secret_name'), str) or not item['secret_name']:
            sys.exit(1)
        if not str(item.get('tls_crt_pem', '')).lstrip().startswith('-----BEGIN CERTIFICATE-----'):
            sys.exit(1)
        if not str(item.get('tls_key_pem', '')).lstrip().startswith('-----BEGIN '):
            sys.exit(1)
        cert = x509.load_pem_x509_certificate(item['tls_crt_pem'].encode())
        key = serialization.load_pem_private_key(item['tls_key_pem'].encode(), password=None)
        encoding = serialization.Encoding.DER
        fmt = serialization.PublicFormat.SubjectPublicKeyInfo
        if cert.public_key().public_bytes(encoding, fmt) != key.public_key().public_bytes(encoding, fmt):
            sys.exit(1)
except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
    sys.exit(1)
PY
    then
      ok 'recovery/recovery.yaml certificate and private key pairs'
    else
      error 'recovery/recovery.yaml is invalid, contains example keys, or Python YAML/cryptography packages are unavailable.'
    fi
  fi
fi

printf 'Credential check: %d error(s), %d warning(s).\n' "$errors" "$warnings"
(( errors == 0 ))
