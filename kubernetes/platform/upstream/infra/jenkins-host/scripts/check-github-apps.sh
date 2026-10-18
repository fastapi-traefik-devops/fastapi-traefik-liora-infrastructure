#!/bin/sh
# Check the fastapi-ci and fastapi-gitops GitHub Apps from their Jenkins secret files: the
# key signs a JWT, GitHub returns the App and its installation, and a short-lived installation
# token shows the granted permissions. Prints names and permissions only, never a key or token.
set -eu
root=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
secrets="$root/.jenkins-host/secrets"
repo=fastapi-traefik-devops/fastapi-traefik-datascientest-project
api=https://api.github.com

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

check() {
  name=$1
  app_id=$(cat "$secrets/github-$name-app-id")
  key="$secrets/github-$name-app-key.pem"
  head -1 "$key" | grep -q -- '-----BEGIN PRIVATE KEY-----' || { echo "$name: key is not PKCS#8" >&2; return 1; }
  now=$(date +%s)
  header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
  payload=$(printf '{"iat":%s,"exp":%s,"iss":"%s"}' "$((now - 60))" "$((now + 540))" "$app_id" | b64url)
  signature=$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$key" -binary | b64url)
  jwt="$header.$payload.$signature"
  installation=$(curl -fsS -H "Authorization: Bearer $jwt" -H 'Accept: application/vnd.github+json' "$api/repos/$repo/installation")
  id=$(printf '%s' "$installation" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
  curl -fsS -X POST -H "Authorization: Bearer $jwt" -H 'Accept: application/vnd.github+json' \
      "$api/app/installations/$id/access_tokens" \
    | python3 -c '
import json, sys
token = json.load(sys.stdin)
selection = token.get("repository_selection")
print(f"{sys.argv[1]}: installed on {sys.argv[2]}, repositories: {selection}")
print("  permissions:", ", ".join(f"{k}={v}" for k, v in sorted(token["permissions"].items())))
' "$name" "$repo"
}

for name in ${*:-ci gitops}; do
  check "$name"
done
