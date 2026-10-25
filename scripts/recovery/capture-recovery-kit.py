#!/usr/bin/env python3
"""Stage required ignored state inside recovery/ for the existing AES ZIP workflow."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys


MODULES = (
    'edge/tailscale/terraform',
    'edge/haproxy/terraform',
    'infrastructure/k3s-cluster/terraform',
)
PLATFORM_RECORDS = (
    'nonprod-monitoring.json',
    'prod-monitoring.json',
    'nonprod-jenkins.json',
)
RECOVERY_INPUTS = (
    '.env', 'recovery.yaml', 'LIORA-id_ed25519', 'LIORA-id_ed25519.pub',
    'cloudflare-dns-token', 'backup-coordinator.json',
    'k3s-nonprod-server.token', 'k3s-prod-server.token',
    'slack-nonprod-normal-webhook', 'slack-nonprod-testing-webhook',
    'slack-prod-normal-webhook', 'slack-prod-testing-webhook',
)


def regular(path):
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValueError('Symlink in input: ' + str(path))
    if not stat.S_ISREG(mode):
        raise ValueError('Required input is not a regular file: ' + str(path))
    return path


def files_under(path):
    if not path.is_dir() or path.is_symlink():
        raise ValueError('Required directory is absent or unsafe: ' + str(path))
    result = []
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs:
            child = Path(parent) / name
            if child.is_symlink():
                raise ValueError('Symlink in input: ' + str(child))
        for name in files:
            result.append(regular(Path(parent) / name))
    if not result:
        raise ValueError('Required directory is empty: ' + str(path))
    return sorted(result)


def capture(repo, backup, destination):
    repo = repo.resolve(strict=True)
    recovery = repo / 'recovery'
    backup = backup.resolve(strict=True)
    if backup.is_relative_to(recovery):
        raise ValueError('Jenkins backup must be outside recovery/')
    for name in RECOVERY_INPUTS:
        regular(recovery / name)
    for name in PLATFORM_RECORDS:
        regular(repo / '.local-work/private/platform' / name)
    regular(backup / 'home.tar.gz')
    manifest = json.loads(regular(backup / 'manifest.json').read_text())
    if manifest.get('mode') != 'stopped-preservation' or manifest.get('consistent') is not True:
        raise ValueError('Jenkins backup is not a completed stopped-home archive')
    archives = manifest.get('archives', [])
    if len(archives) != 1 or archives[0].get('file') != 'home.tar.gz':
        raise ValueError('Jenkins archive manifest does not identify home.tar.gz')
    home = backup / 'home.tar.gz'
    if home.stat().st_size != archives[0].get('bytes'):
        raise ValueError('Jenkins archive size differs from its manifest')
    with home.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != archives[0].get('sha256'):
        raise ValueError('Jenkins archive checksum differs from its manifest')
    regular(backup / 'deployment-before.json')
    if not list(backup.glob('configmap-*.json')):
        raise ValueError('Jenkins backup has no mounted ConfigMap records')
    if destination.exists():
        raise ValueError('Destination already exists; preserve and choose a new name')
    if destination.parent != recovery:
        raise ValueError('Destination must be a direct child of recovery/')

    inputs = []
    for module in MODULES:
        folder = repo / module
        inputs.append(regular(folder / 'terraform.tfstate'))
        inputs += sorted(regular(path) for path in folder.glob('terraform.tfstate.*'))
        inputs += sorted(regular(path) for path in folder.glob('*.tfvars'))
        lock = folder / '.terraform.lock.hcl'
        if lock.exists():
            inputs.append(regular(lock))
    inputs += [repo / '.local-work/private/platform' / name for name in PLATFORM_RECORDS]
    inputs += files_under(backup)

    os.mkdir(destination, 0o700)
    records = []
    try:
        for source in inputs:
            source = regular(source)
            if source.is_relative_to(backup):
                relative = Path('jenkins-backup') / source.relative_to(backup)
            elif source.is_relative_to(repo):
                relative = source.relative_to(repo)
            else:
                raise ValueError('Unrecognized capture source')
            target = destination / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            before = source.lstat()
            source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(source_fd, 'rb') as incoming, target.open('xb') as outgoing:
                opened = os.fstat(incoming.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError('Input changed during capture')
                digest = hashlib.sha256()
                while chunk := incoming.read(1024 * 1024):
                    outgoing.write(chunk)
                    digest.update(chunk)
                after = os.fstat(incoming.fileno())
                if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                        after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('Input changed during capture')
            target.chmod(0o600)
            records.append({'path': relative.as_posix(), 'sha256': digest.hexdigest()})
        manifest = {'version': 1, 'files': records,
                    'recovery_inputs': list(RECOVERY_INPUTS)}
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (destination / 'manifest.json').chmod(0o600)
    except BaseException:
        # Never leave a partial directory that the archive helper could include.
        shutil.rmtree(destination)
        raise
    print('Recovery kit staged: ' + str(destination))
    print('Additional private files: ' + str(len(records)))


def verify(destination):
    manifest = json.loads(regular(destination / 'manifest.json').read_text())
    if manifest.get('version') != 1 or not isinstance(manifest.get('files'), list):
        raise ValueError('Invalid capture manifest')
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe capture manifest path')
        path = regular(destination / relative)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != entry['sha256']:
            raise ValueError('Capture checksum mismatch: ' + relative.as_posix())
    print('Capture integrity verified: ' + str(len(manifest['files'])) + ' files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--jenkins-backup', type=Path)
    parser.add_argument('--name', help='New directory name under recovery/')
    parser.add_argument('--verify', type=Path, help='Verify an extracted kit directory')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.verify:
            if args.name or args.jenkins_backup:
                parser.error('--verify cannot be combined with capture options')
            verify(args.verify)
        else:
            if not args.name or not args.name.startswith('kit-') or '/' in args.name or args.name in ('.', '..'):
                parser.error('Use a new kit-... directory name without slashes')
            if not args.jenkins_backup:
                parser.error('--jenkins-backup is required for capture')
            capture(args.repo, args.jenkins_backup, args.repo.resolve() / 'recovery' / args.name)
    except (OSError, ValueError) as error:
        print('Capture stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
