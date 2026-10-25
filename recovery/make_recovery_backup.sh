#!/usr/bin/env bash
# Create an AES-256 ZIP of recovery/ files that are not tracked by Git.
# Run from any directory. Password input requires an interactive terminal.
# Dependency: pyzipper==0.4.0, pycryptodomex==3.23.0 (isolated venv supported).
set -euo pipefail
umask 077

recovery_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_dir="$(git -C "$recovery_dir" rev-parse --show-toplevel)"
python=''
for candidate in "$repo_dir/.local-work/recovery-zip-venv/bin/python" \
                 "$repo_dir/.local-work/venv/bin/python" python3; do
  if "$candidate" -c 'import pyzipper, importlib.metadata; assert importlib.metadata.version("pyzipper") == "0.4.0"' >/dev/null 2>&1; then
    python="$candidate"
    break
  fi
done
if [[ -z "$python" ]]; then
  printf 'Required AES ZIP dependency is missing. Run once:\n' >&2
  printf 'python3 -m venv %q\n' "$repo_dir/.local-work/recovery-zip-venv" >&2
  printf '%q -m pip install pyzipper==0.4.0 pycryptodomex==3.23.0\n' \
    "$repo_dir/.local-work/recovery-zip-venv/bin/python" >&2
  exit 1
fi

exec "$python" - "$repo_dir" "$recovery_dir" <<'PY'
import datetime as dt
import getpass
import os
from pathlib import Path
import stat
import sys
import tempfile

import pyzipper
sys.path.insert(0, str(Path(sys.argv[1]) / 'recovery'))
from archive_inventory import select

repo = Path(sys.argv[1])
source = Path(sys.argv[2])
archive_path = None
complete = False
try:
    if source != repo / 'recovery':
        raise RuntimeError('Run the script from the repository recovery directory')
    files, directories = select(repo, source)

    # getpass reads /dev/tty; never accept an echoed or command-line password.
    with open('/dev/tty', 'w') as terminal:
        print('Source: ' + str(source), file=terminal)
        print('Git-tracked files are excluded. Files to back up: ' + str(len(files)), file=terminal)
        password = getpass.getpass('Archive password (required): ', stream=terminal)
        if not password.strip():
            raise RuntimeError('The archive password must not be empty')
        confirmation = getpass.getpass('Confirm archive password: ', stream=terminal)
        if password != confirmation:
            raise RuntimeError('Passwords do not match')

    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    # mkstemp reserves a unique name without overwriting any existing archive.
    fd, name = tempfile.mkstemp(prefix='liora-recovery-' + stamp + '-', suffix='.zip', dir=Path.home())
    archive_path = Path(name)
    with os.fdopen(fd, 'w+b') as stream:
        with pyzipper.AESZipFile(stream, 'w', compression=pyzipper.ZIP_DEFLATED,
                                encryption=pyzipper.WZ_AES, allowZip64=True) as archive:
            archive.setpassword(password.encode('utf-8'))
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            for path, relative in directories:
                archive.write(str(path), relative)
            for path, relative in files:
                before = path.lstat()
                if not stat.S_ISREG(before.st_mode):
                    raise RuntimeError('A source file changed type during backup')
                # O_NOFOLLOW prevents a changed symlink from escaping recovery/.
                source_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(source_fd, 'rb') as incoming:
                    opened = os.fstat(incoming.fileno())
                    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                        raise RuntimeError('A source file was replaced during backup')
                    info = archive.zipinfo_cls.from_file(str(path), relative)
                    info.compress_type = pyzipper.ZIP_DEFLATED
                    with archive.open(info, 'w', force_zip64=True) as outgoing:
                        while chunk := incoming.read(1024 * 1024):
                            outgoing.write(chunk)
                    after = os.fstat(incoming.fileno())
                    if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise RuntimeError('A source file changed during backup; run again when writes stop')
        stream.flush()
        os.fsync(stream.fileno())

    # Verify authentication and decompression before announcing success.
    with pyzipper.AESZipFile(str(archive_path), 'r') as archive:
        archive.setpassword(password.encode('utf-8'))
        for info in archive.infolist():
            with archive.open(info) as incoming:
                while incoming.read(1024 * 1024):
                    pass
    complete = True
    print('Recovery backup created successfully (AES-256 ZIP).')
    print('Archive: ' + str(archive_path.resolve()))
    print('Files: ' + str(len(files)))
    print('Permissions: 0600. Datetime in filename: UTC.')
except (KeyboardInterrupt, EOFError):
    print('Backup cancelled; no complete archive was created.', file=sys.stderr)
    sys.exit(1)
except RuntimeError as error:
    # Only our fixed messages are shown; library errors may contain private data.
    messages = {
        'Run the script from the repository recovery directory',
        'Symbolic links are not supported; no backup was created',
        'A non-regular recovery file prevents a complete backup',
        'No untracked recovery files to back up',
        'The archive password must not be empty',
        'Passwords do not match',
        'A source file changed type during backup',
        'A source file was replaced during backup',
        'A source file changed during backup; run again when writes stop',
    }
    print('Backup failed: ' + (str(error) if str(error) in messages else type(error).__name__), file=sys.stderr)
    sys.exit(1)
except Exception as error:
    print('Backup failed (' + type(error).__name__ + '); no complete archive was created.', file=sys.stderr)
    sys.exit(1)
finally:
    if archive_path is not None and not complete:
        archive_path.unlink(missing_ok=True)
PY
