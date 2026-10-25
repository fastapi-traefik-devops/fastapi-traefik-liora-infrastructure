#!/usr/bin/env python3
"""Prepare a private, inactive Jenkins archive; never extract or start it."""

import argparse
import copy
import datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
import xml.etree.ElementTree as ET


HOLD = b'''// Migration hold: retain until reviewed activation.
import jenkins.model.Jenkins
def controller = Jenkins.get()
controller.setNumExecutors(0)
controller.doQuietDown(false, 0, "Migration validation: jobs held", false)
controller.getQueue().clear()
assert controller.isQuietingDown()
'''
JOB_TYPES = {'flow-definition', 'project',
             'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject'}
FOLDER = 'com.cloudbees.hudson.plugins.folder.Folder'
KEYS = {'secrets/master.key', 'secrets/hudson.util.Secret'}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def normalized(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError('Unsafe archive path')
    return str(path)


def edit_config(data, controller=False):
    root = ET.fromstring(data)
    if not controller and root.tag not in JOB_TYPES | {FOLDER}:
        raise ValueError('Unreviewed job type')
    # Both folder scanning and workflow timer/SCM triggers must remain inactive.
    # Drop obsolete job-level Declarative bookkeeping too: deleting its nested
    # triggers set leaves a null field that crashes the next Pipeline startup.
    # Build records are copied unchanged and never pass through this function.
    for parent in root.iter():
        for child in list(parent):
            if child.tag in {'triggers', 'org.jenkinsci.plugins.pipeline.modeldefinition.actions.DeclarativeJobPropertyTrackerAction'}:
                parent.remove(child)
    if controller:
        for name in ('clouds', 'slaves'):
            for element in root.findall(name):
                root.remove(element)
        for name, value in [('numExecutors', '0'), ('slaveAgentPort', '-1')]:
            element = root.find(name)
            if element is None:
                element = ET.SubElement(root, name)
            element.text = value
    elif root.tag in JOB_TYPES:
        disabled = root.find('disabled')
        if disabled is None:
            disabled = ET.SubElement(root, 'disabled')
        disabled.text = 'true'
        if root.tag == 'flow-definition':
            properties = root.find('properties')
            if properties is None:
                properties = ET.SubElement(root, 'properties')
            name = 'org.jenkinsci.plugins.workflow.job.properties.DisableResumeJobProperty'
            if properties.find(name) is None:
                ET.SubElement(properties, name)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def stage(source, destination, admin_config=None):
    """Stream a verified backup to a new private directory, without extraction."""
    manifest = json.loads((source / 'manifest.json').read_text())
    records = [record for record in manifest['archives'] if record['file'] == 'home.tar.gz']
    stopped = manifest.get('mode') == 'stopped-preservation' and manifest.get('consistent') is True
    if len(records) != 1 or not (stopped or manifest.get('mode') == 'online-preservation-only'):
        raise ValueError('Unsupported preservation manifest')
    home = source / 'home.tar.gz'
    if digest(home) != records[0]['sha256'] or home.stat().st_size != records[0]['bytes']:
        raise ValueError('Source integrity mismatch')
    admin_path, admin_data = None, None
    if admin_config is not None:
        if not stopped or admin_config.stat().st_mode & 0o077:
            raise ValueError('Admin input requires stopped source and private file permissions')
        admin_data = admin_config.read_bytes()
        user = ET.fromstring(admin_data)
        if user.tag != 'user' or user.findtext('id') != 'admin' or not user.findtext('.//passwordHash'):
            raise ValueError('Expected the current admin login configuration')
        # User-scoped encrypted credentials would require the foundation keys;
        # do not silently combine those with the preserved legacy controller keys.
        for element in user.iter('domainCredentialsMap'):
            if len(element):
                raise ValueError('Admin has user credentials requiring separate key migration')
        candidates = []
        with tarfile.open(home, 'r:gz') as archive:
            for member in archive:
                name = normalized(member.name)
                if member.isfile() and name.startswith('users/') and name.endswith('/config.xml'):
                    if ET.fromstring(archive.extractfile(member).read()).findtext('id') == 'admin':
                        candidates.append(name)
        if len(candidates) != 1:
            raise ValueError('Expected exactly one legacy admin directory')
        # Jenkins 2.585 derives the directory from secrets/hudson.model.User.DIRNAMES.
        # Retain that source salt and replace account bytes at its expected path.
        admin_path = candidates[0]
    if stopped and admin_config is None:
        with tarfile.open(home, 'r:gz') as archive:
            admins = [ET.fromstring(archive.extractfile(member).read()) for member in archive
                      if member.isfile() and normalized(member.name).startswith('users/')
                      and normalized(member.name).endswith('/config.xml')]
        if sum(user.findtext('id') == 'admin' and bool(user.findtext('.//passwordHash')) for user in admins) != 1:
            raise ValueError('Archive must contain exactly one complete administrator account')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    target = destination / 'inactive-home.tar.gz'
    counts = {'job_configs': 0, 'build_records': 0, 'user_configs': 0,
              'omitted_members': 0, 'copied_files': 0}
    seen, preserved_keys = set(), set()
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
        with tarfile.open(home, 'r:gz') as original, tarfile.open(fileobj=output, mode='w:gz') as staged:
            for member in original:
                name = normalized(member.name)
                if name in seen:
                    raise ValueError('Duplicate archive member')
                seen.add(name)
                if not (member.isfile() or member.isdir()):
                    raise ValueError('Links or special archive entries require review')
                parts = PurePosixPath(name).parts
                if (parts and parts[0] in {'nodes', 'init.groovy.d'} or
                        name in {'init.groovy', 'queue.xml', 'queue.xml.bak'} or
                        admin_path and name.startswith(admin_path.removesuffix('config.xml')) and
                        name != admin_path and member.isfile()):
                    counts['omitted_members'] += 1
                    continue
                data = None
                if member.isfile():
                    stream = original.extractfile(member)
                    if name == admin_path:
                        data = admin_data
                    elif name == 'config.xml' or (name.startswith('jobs/') and name.endswith('/config.xml')):
                        data = edit_config(stream.read(), controller=name == 'config.xml')
                        counts['job_configs'] += int(name != 'config.xml')
                    else:
                        data = stream
                    counts['build_records'] += int(name.startswith('jobs/') and name.endswith('/build.xml'))
                    counts['user_configs'] += int(name.startswith('users/') and name.endswith('/config.xml'))
                    counts['copied_files'] += 1
                    if name in KEYS:
                        preserved_keys.add(name)
                entry = copy.copy(member)
                entry.name = name
                if isinstance(data, bytes):
                    entry.size = len(data)
                    data = io.BytesIO(data)
                staged.addfile(entry, data)
            if not KEYS <= preserved_keys or 'config.xml' not in seen:
                raise ValueError('Required controller recovery state missing')
            hook = tarfile.TarInfo('init.groovy.d/00-migration-hold.groovy')
            hook.mode, hook.uid, hook.gid, hook.size = 0o600, 1000, 1000, len(HOLD)
            staged.addfile(hook, io.BytesIO(HOLD))
    result = {'mode': 'offline-inactive-restore-candidate' if stopped else 'offline-inactive-preview',
              'consistent': stopped, 'admin_login_preserved': stopped, 'restore_tested': False,
              'ready_for_cutover': False, 'source_sha256': records[0]['sha256'],
              'archive_sha256': digest(target), 'counts': counts,
              'warning': 'No runtime hold or restore has been tested.' if stopped else
                         'Online source; not a final backup. No runtime hold or restore has been tested.'}
    with os.fdopen(os.open(destination / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup_directory', type=Path)
    parser.add_argument('--admin-config', type=Path, help='Private current K3s admin XML for stopped-source migration')
    arguments = parser.parse_args()
    private = Path(__file__).resolve().parents[2] / '.local-work/private/phase9'
    destination = private / ('staged-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    result = stage(arguments.backup_directory, destination, arguments.admin_config)
    print(json.dumps({'staging_directory': str(destination), **result}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # XML/parser/tar errors can contain source contents or paths. Never echo them.
        print(json.dumps({'staging_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
