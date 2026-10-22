#!/usr/bin/env python3
"""Verify inactive-copy transformations and preservation without leaking values."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / 'stage-jenkins-home.py'
SECRET = 'FIXTURE-SECRET-ONLY-72c44d'


class StagingTests(unittest.TestCase):
    def invoke(self, alteration=None):
        files = {
            'config.xml': b'<hudson><numExecutors>2</numExecutors><slaveAgentPort>50000</slaveAgentPort><clouds><cloud/></clouds><securityRealm>keep</securityRealm></hudson>',
            'jobs/ci/config.xml': b'<flow-definition><disabled>false</disabled><properties><pipeline><triggers><timer>schedule</timer></triggers></pipeline></properties></flow-definition>',
            'jobs/branches/config.xml': b'<org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject><triggers><timer/></triggers></org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject>',
            'jobs/trusted/config.xml': b'<com.cloudbees.hudson.plugins.folder.Folder><credentials>keep</credentials></com.cloudbees.hudson.plugins.folder.Folder>',
            'secrets/master.key': SECRET.encode(),
            'secrets/hudson.util.Secret': SECRET.encode(),
            'users/admin/config.xml': ('<user><passwordHash>' + SECRET + '</passwordHash></user>').encode(),
            'jobs/ci/builds/1/build.xml': ('<build>' + SECRET + '</build>').encode(),
            'jobs/trusted/credentials.xml': SECRET.encode(),
            'jobs/ci/builds/1/archive/artifact.bin': SECRET.encode(),
            'queue.xml': SECRET.encode(),
            'nodes/old/config.xml': SECRET.encode(),
            'init.groovy.d/old.groovy': SECRET.encode(),
        }
        if alteration:
            alteration(files)
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[2] / '.local-work') as directory:
            root = Path(directory)
            script = root / 'scripts/kubernetes/stage-jenkins-home.py'
            script.parent.mkdir(parents=True)
            script.write_text(SCRIPT.read_text())
            source = root / 'source'
            source.mkdir()
            home = source / 'home.tar.gz'
            with tarfile.open(home, 'w:gz') as archive:
                for name, data in files.items():
                    entry = tarfile.TarInfo(name)
                    if data is None:
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = SECRET
                        archive.addfile(entry)
                        continue
                    entry.size = len(data)
                    archive.addfile(entry, io.BytesIO(data))
            manifest = {'mode': 'online-preservation-only', 'archives': [
                {'file': home.name, 'bytes': home.stat().st_size,
                 'sha256': hashlib.sha256(home.read_bytes()).hexdigest()}]}
            if alteration == corrupt_digest:
                manifest['archives'][0]['sha256'] = '0' * 64
            (source / 'manifest.json').write_text(json.dumps(manifest))
            source_digest = hashlib.sha256(home.read_bytes()).hexdigest()
            stdout, stderr = io.StringIO(), io.StringIO()
            status = 0
            with patch.object(sys, 'argv', [str(script), str(source)]), redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    runpy.run_path(str(script), run_name='__main__')
                except SystemExit as error:
                    status = error.code
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
            # Source material is never rewritten, including after failed staging.
            self.assertEqual(hashlib.sha256(home.read_bytes()).hexdigest(), source_digest)
            if alteration:
                self.assertEqual(status, 1)
                self.assertFalse(list(root.glob('.local-work/private/phase9/*/manifest.json')))
                return
            self.assertEqual(status, 0)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result['consistent'])
            self.assertFalse(result['restore_tested'])
            self.assertFalse(result['ready_for_cutover'])
            self.assertEqual(result['counts']['job_configs'], 3)
            self.assertEqual(result['counts']['build_records'], 1)
            destination = Path(result['staging_directory'])
            self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
            for file in destination.iterdir():
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            with tarfile.open(destination / 'inactive-home.tar.gz') as archive:
                output = {entry.name: archive.extractfile(entry).read() for entry in archive if entry.isfile()}
            for name, data in files.items():
                if name == 'queue.xml' or name.startswith(('nodes/', 'init.groovy.d/')):
                    self.assertNotIn(name, output)
                elif name == 'config.xml':
                    config = ET.fromstring(output[name])
                    self.assertEqual(config.findtext('numExecutors'), '0')
                    self.assertEqual(config.findtext('slaveAgentPort'), '-1')
                    self.assertIsNone(config.find('clouds'))
                    self.assertEqual(config.findtext('securityRealm'), 'keep')
                elif name.startswith('jobs/') and name.endswith('/config.xml'):
                    config = ET.fromstring(output[name])
                    self.assertFalse(list(config.iter('triggers')))
                    if config.tag != 'com.cloudbees.hudson.plugins.folder.Folder':
                        self.assertEqual(config.findtext('disabled'), 'true')
                    if config.tag == 'flow-definition':
                        self.assertIsNotNone(config.find('properties/org.jenkinsci.plugins.workflow.job.properties.DisableResumeJobProperty'))
                else:
                    self.assertEqual(output[name], data)
            self.assertIn(b'doQuietDown', output['init.groovy.d/00-migration-hold.groovy'])

    def test_preserves_private_history_and_keys_in_inactive_copy(self):
        self.invoke()

    def test_rejects_missing_key_without_leak(self):
        self.invoke(lambda files: files.pop('secrets/master.key'))

    def test_rejects_path_traversal_without_leak(self):
        self.invoke(lambda files: files.update({'../' + SECRET: b'bad'}))

    def test_rejects_unreviewed_job_type(self):
        self.invoke(lambda files: files.update({'jobs/ci/config.xml': b'<unknown/>'}))

    def test_xml_error_does_not_print_private_values(self):
        self.invoke(lambda files: files.update({'config.xml': ('<' + SECRET).encode()}))

    def test_rejects_integrity_mismatch(self):
        self.invoke(corrupt_digest)

    def test_rejects_links_without_printing_the_target(self):
        self.invoke(lambda files: files.update({'unsafe-link': None}))

    def test_rejects_duplicate_normalized_paths(self):
        self.invoke(lambda files: files.update({'./config.xml': files['config.xml']}))


def corrupt_digest(files):
    pass


if __name__ == '__main__':
    unittest.main()
