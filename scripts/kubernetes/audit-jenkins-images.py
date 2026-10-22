#!/usr/bin/env python3
"""Apply the preserved HIGH/CRITICAL image gate without starting Jenkins jobs."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_report(path, layers):
    """Reject incomplete scans and reports for a different image filesystem."""
    report = json.loads(path.read_text())
    metadata = report.get('Metadata', {})
    if (report.get('SchemaVersion') != 2 or report.get('ArtifactType') != 'container_image'
            or not layers or metadata.get('DiffIDs') != layers
            or not isinstance(report.get('Results'), list) or not report['Results']):
        raise RuntimeError('Incomplete or mismatched image report')
    findings = []
    for target in report['Results']:
        for finding in target.get('Vulnerabilities') or []:
            findings.append({key: finding.get(key) for key in
                             ['VulnerabilityID', 'PkgName', 'Severity', 'InstalledVersion', 'FixedVersion']})
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', action='append', help='Local image to scan; repeat for multiple images')
    args = parser.parse_args()
    os.umask(0o077)
    images = args.image or ['phase1/jenkins-' + name + ':local' for name in ('controller', 'agent', 'dind')]
    scanner = ROOT / '.local-work/tools/trivy'
    if not scanner.is_file():
        raise RuntimeError('Prepare the source-built scanner before auditing images')
    base = ROOT / '.local-work/phase9'
    directory = base / ('image-audit-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    cache = base / 'trivy-cache'
    cache.mkdir(mode=0o700, exist_ok=True)
    scanner_hash = file_sha256(scanner)
    results = []
    for index, image in enumerate(images):
        if shutil.disk_usage(directory).free < 2 * 1024**3:
            raise RuntimeError('Need 2GiB free for the sequential image audit')
        inspected = subprocess.run(['docker', 'image', 'inspect', image, '--format',
                                    '{"id":{{json .Id}},"layers":{{json .RootFS.Layers}}}'], capture_output=True)
        if inspected.returncode:
            raise RuntimeError('Required source image is unavailable')
        identity = json.loads(inspected.stdout)
        image_id = identity['id']
        report = directory / f'image-{index}.json'
        with tempfile.TemporaryDirectory(prefix='scan-', dir=directory) as scratch:
            archive = Path(scratch) / 'image.tar'
            exported = subprocess.run(['docker', 'save', '-o', str(archive), image_id], capture_output=True)
            if exported.returncode:
                raise RuntimeError('Image export failed')
            archive_hash = file_sha256(archive)
            command = ['docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                       '--memory', '3g', '--memory-swap', '3g', '--cpus', '1',
                       '-e', 'HOME=/tmp', '-e', 'GOMEMLIMIT=1200MiB',
                       '-v', f'{scanner}:/scanner:ro', '-v', f'{scratch}:/scan:ro',
                       '-v', f'{directory}:/reports', '-v', f'{cache}:/cache',
                       '--entrypoint', '/scanner', 'phase1/jenkins-controller:local',
                       'image', '--scanners', 'vuln', '--parallel', '1', '--severity', 'HIGH,CRITICAL',
                       '--exit-code', '1', '--no-progress', '--timeout', '10m', '--format', 'json',
                       '--cache-dir', '/cache', '--input', '/scan/image.tar', '--output', '/reports/' + report.name]
            status = subprocess.run(command, capture_output=True)
            (directory / f'image-{index}.log').write_bytes(status.stdout + status.stderr)
        # Remove only this invocation's disposable export, never source images,
        # legacy volumes, recovery archives or operator files.
        findings = []
        if report.exists():
            report.chmod(0o600)
            findings = read_report(report, identity['layers'])
        passed = status.returncode == 0 and report.exists() and not findings
        result = {'image': image, 'image_id': image_id, 'passed': passed, 'scanner_exit': status.returncode,
                  'scanner_sha256': scanner_hash, 'archive_sha256': archive_hash,
                  'report_sha256': file_sha256(report) if report.exists() else None,
                  'findings': findings, 'report': str(report)}
        results.append(result)
        (directory / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    return 0 if all(result['passed'] for result in results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'audit_complete': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
