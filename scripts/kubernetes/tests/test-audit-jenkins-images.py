#!/usr/bin/env python3
"""Exercise the image gate's fail-closed behavior without Docker or networking."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'audit-jenkins-images.py'
MODULE = runpy.run_path(str(SCRIPT))
SECRET = 'FAKE-AUDIT-ERROR-SECRET-ONLY-907c'


class AuditTests(unittest.TestCase):
    def report(self):
        return {'SchemaVersion': 2, 'ArtifactType': 'container_image',
                'Metadata': {'DiffIDs': ['sha256:fixture-layer']},
                'Results': [{'Vulnerabilities': None}]}

    def test_complete_clean_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            path.write_text(json.dumps(self.report()))
            self.assertEqual(MODULE['read_report'](path, ['sha256:fixture-layer']), [])

    def test_incomplete_and_wrong_image_reports_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            for report in [{}, {**self.report(), 'Results': []},
                           {**self.report(), 'Metadata': {'DiffIDs': ['sha256:other']}}]:
                path.write_text(json.dumps(report))
                with self.assertRaises(RuntimeError):
                    MODULE['read_report'](path, ['sha256:fixture-layer'])

    def invoke(self, scanner_status=0, with_report=True, vulnerability=False, export_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scanner = root / 'trivy'
            scanner.write_bytes(b'fixture scanner')
            image_id = 'sha256:fixture-image'

            def command(arguments, **kwargs):
                if arguments[1:3] == ['image', 'inspect']:
                    return subprocess.CompletedProcess(arguments, 0,
                        json.dumps({'id': image_id, 'layers': ['sha256:fixture-layer']}).encode(), b'')
                if arguments[1] == 'save':
                    Path(arguments[3]).write_bytes(b'fixture image')
                    return subprocess.CompletedProcess(arguments, int(export_failure), b'', SECRET.encode())
                self.assertIn('--cap-drop', arguments)
                self.assertNotIn('--ignore-unfixed', arguments)
                self.assertNotIn('--skip-java-db-update', arguments)
                self.assertIn('HIGH,CRITICAL', arguments)
                self.assertIn('3g', arguments)
                reports = next(Path(value.removesuffix(':/reports')) for value in arguments if value.endswith(':/reports'))
                if with_report:
                    report = self.report()
                    if vulnerability:
                        report['Results'][0]['Vulnerabilities'] = [dict(VulnerabilityID='CVE-2099-0001', Severity='HIGH')]
                    (reports / 'image-0.json').write_text(json.dumps(report))
                return subprocess.CompletedProcess(arguments, scanner_status, b'', SECRET.encode())

            original_path = Path.is_file

            def is_file(path):
                return True if path.name == 'trivy' else original_path(path)

            # Keep the real script path for ROOT, redirect only private output paths.
            original_resolve = Path.resolve

            def resolve(path, **kwargs):
                return root / 'scripts/kubernetes/audit-jenkins-images.py' if path == SCRIPT else original_resolve(path, **kwargs)

            tools = root / '.local-work/tools'
            tools.mkdir(parents=True)
            (tools / 'trivy').write_bytes(scanner.read_bytes())
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch('subprocess.run', side_effect=command), \
                    patch.object(Path, 'resolve', resolve), patch.object(Path, 'is_file', is_file), \
                    patch('shutil.disk_usage', return_value=type('Disk', (), {'free': 10 * 1024**3})()), \
                    patch.object(sys, 'argv', [str(SCRIPT), '--image', 'fixture:local']), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as status:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
            expected = 1 if scanner_status or not with_report or vulnerability or export_failure else 0
            self.assertEqual(status.exception.code, expected)
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
            self.assertFalse(list(root.glob('.local-work/phase9/image-audit-*/scan-*')))

    def test_success_preserves_provenance_without_private_output(self):
        self.invoke()

    def test_scanner_error_cannot_pass_with_clean_report(self):
        self.invoke(scanner_status=137)

    def test_missing_report_cannot_pass(self):
        self.invoke(with_report=False)

    def test_vulnerabilities_cannot_pass_even_with_zero_status(self):
        self.invoke(vulnerability=True)

    def test_export_error_does_not_print_private_diagnostics(self):
        self.invoke(export_failure=True)


if __name__ == '__main__':
    unittest.main()
