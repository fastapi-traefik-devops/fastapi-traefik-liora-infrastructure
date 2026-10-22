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
    for parent in root.iter():
        for child in list(parent):
            if child.tag == 'triggers':
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


def stage(source, destination):
    """Stream a verified backup to a new private directory, without extraction."""
    manifest = json.loads((source / 'manifest.json').read_text())
    records = [record for record in manifest['archives'] if record['file'] == 'home.tar.gz']
    if len(records) != 1 or manifest.get('mode') != 'online-preservation-only':
        raise ValueError('Expected an online preservation manifest')
    home = source / 'home.tar.gz'
    if digest(home) != records[0]['sha256'] or home.stat().st_size != records[0]['bytes']:
        raise ValueError('Source integrity mismatch')
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
                        name in {'init.groovy', 'queue.xml', 'queue.xml.bak'}):
                    counts['omitted_members'] += 1
                    continue
                data = None
                if member.isfile():
                    stream = original.extractfile(member)
                    if name == 'config.xml' or (name.startswith('jobs/') and name.endswith('/config.xml')):
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
    result = {'mode': 'offline-inactive-preview', 'consistent': False, 'restore_tested': False,
              'ready_for_cutover': False, 'source_sha256': records[0]['sha256'],
              'archive_sha256': digest(target), 'counts': counts,
              'warning': 'Online source; not a final backup. No runtime hold or restore has been tested.'}
    with os.fdopen(os.open(destination / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup_directory', type=Path)
    arguments = parser.parse_args()
    private = Path(__file__).resolve().parents[2] / '.local-work/private/phase9'
    destination = private / ('staged-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    result = stage(arguments.backup_directory, destination)
    print(json.dumps({'staging_directory': str(destination), **result}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # XML/parser/tar errors can contain source contents or paths. Never echo them.
        print(json.dumps({'staging_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
