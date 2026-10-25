# Unpack the credentials ZIP on the laptop

**Where:** Trusted laptop, infrastructure repository root. Use this procedure
for both a fresh installation and disaster recovery.

## Preflight

- [ ] Keep the encrypted ZIP outside Git. Obtain its password from the
      separate password source.
- [ ] Check for the 7-Zip console command: `command -v 7zz || command -v 7z`.
      If neither exists, install the console version for your laptop from
      the [official 7-Zip downloads](https://www.7-zip.org/download.html).
      This tool supports encrypted ZIP archives.
- [ ] Check the repository: `git rev-parse --show-toplevel`.
      Continue only in the infrastructure checkout.
- [ ] Check `recovery/` for existing private files. If it already has
      credentials from another host or incident, protect and move those
      files before this import. The block below refuses to overwrite
      the required files.

## Extract and copy

- [ ] Run this block. Enter the ZIP path at the prompt. 7-Zip asks for
      the archive password. Do not add the password to a command:

```bash
(
set -euo pipefail
umask 077
read -r -p 'Encrypted credentials ZIP path: ' archive_path
test -f "$archive_path"
mkdir -p .local-work
import_dir="$(mktemp -d .local-work/recovery-import.XXXXXXXX)"
trap 'rm -rf -- "$import_dir"' EXIT
if command -v 7zz >/dev/null 2>&1; then
  zip_tool=7zz
else
  zip_tool=7z
fi
"$zip_tool" x "$archive_path" "-o$import_dir"
key_count="$(find "$import_dir" -type f -name LIORA-id_ed25519 | wc -l | tr -d ' ')"
test "$key_count" -eq 1
key_file="$(find "$import_dir" -type f -name LIORA-id_ed25519 -print -quit)"
input_dir="$(dirname "$key_file")"
test -z "$(find "$input_dir" -type l -print -quit)"
while IFS= read -r -d '' source_file; do
  relative="${source_file#"$input_dir"/}"
  if git ls-files --error-unmatch -- "recovery/$relative" >/dev/null 2>&1; then
    echo "Archive contains tracked source: recovery/$relative" >&2
    exit 1
  fi
done < <(find "$input_dir" -type f -print0)
for name in .env recovery.yaml LIORA-id_ed25519 LIORA-id_ed25519.pub; do
  test -f "$input_dir/$name" && test ! -L "$input_dir/$name" &&
    test -s "$input_dir/$name"
  test ! -e "recovery/$name" || {
    echo "Existing recovery/$name; inspect it before importing" >&2
    exit 1
  }
done
mkdir -p recovery
cp -R -p "$input_dir"/. recovery/
chmod 700 recovery
chmod 600 recovery/.env recovery/recovery.yaml recovery/LIORA-id_ed25519
for private_file in recovery/k3s-*.token recovery/cloudflare-dns-token recovery/backup-coordinator.json; do
  if test -f "$private_file"; then chmod 600 "$private_file"; fi
done
git check-ignore recovery/.env recovery/recovery.yaml recovery/LIORA-id_ed25519
test -z "$(git ls-files --others --exclude-standard recovery/)"
)
```

- [ ] Check that the required files exist. Do not print secret values:

```sh
ls -l recovery/.env recovery/recovery.yaml \
  recovery/LIORA-id_ed25519 recovery/LIORA-id_ed25519.pub
```

**Done when:** The ignored `recovery/` directory contains the archived
credentials and SSH pair. Keep the original ZIP and its password in their
separate protected locations.
