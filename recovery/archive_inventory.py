"""Select only untracked regular recovery files for the AES ZIP helper."""

import os
from pathlib import Path
import stat
import subprocess


def select(repo: Path, source: Path):
    raw = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z', '--', 'recovery/'])
    tracked = {os.fsdecode(name) for name in raw.split(b'\0') if name}
    files = []
    directories = []

    def walk_error(error):
        raise error

    for directory, names, filenames in os.walk(source, followlinks=False, onerror=walk_error):
        names.sort()
        filenames.sort()
        for name in names + filenames:
            path = Path(directory) / name
            relative = path.relative_to(repo).as_posix()
            if relative in tracked or relative == 'recovery/make_recovery_backup.sh':
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise RuntimeError('Symbolic links are not supported; no backup was created')
            if stat.S_ISDIR(mode):
                directories.append((path, relative + '/'))
            elif stat.S_ISREG(mode):
                files.append((path, relative))
            else:
                raise RuntimeError('A non-regular recovery file prevents a complete backup')
    if not files:
        raise RuntimeError('No untracked recovery files to back up')
    return files, directories
