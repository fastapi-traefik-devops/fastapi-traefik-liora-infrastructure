#!/usr/bin/env python3
"""Fail closed on High/Critical advisories in the Docker Jenkins infrastructure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / ".ci-security"


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    scanner = ROOT / ".tools/phase1/trivy"
    local = str(scanner) if scanner.is_file() else shutil.which("trivy")
    failed = []
    for name in ("controller", "agent", "dind"):
        image = f"phase1/jenkins-{name}:local"
        report = REPORTS / f"jenkins-{name}.json"
        with tempfile.TemporaryDirectory(prefix="phase1-ci-image-") as directory:
            archive = Path(directory) / "image.tar"
            subprocess.run(["docker", "save", "-o", str(archive), image], check=True)
            flags = ["image", "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--exit-code", "1",
                     "--no-progress", "--timeout", "10m", "--format", "json"]
            if local:
                command = [local, *flags, "--input", str(archive), "--output", str(report)]
            else:
                cache = REPORTS / "trivy-cache"
                cache.mkdir(exist_ok=True)
                command = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                           "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                           "--memory", "1g", "-e", "HOME=/tmp", "-v", f"{directory}:/scan:ro",
                           "-v", f"{REPORTS}:/reports", "--entrypoint", "trivy", "phase1/jenkins-agent:local",
                           *flags, "--cache-dir", "/reports/trivy-cache", "--input", "/scan/image.tar",
                           "--output", f"/reports/{report.name}"]
            status = subprocess.run(command).returncode
        if status:
            failed.append(name)
        elif not report.is_file():
            failed.append(name)
        else:
            results = json.loads(report.read_text()).get("Results", [])
            if any(result.get("Vulnerabilities") for result in results):
                failed.append(name)
        print(f"{'FAIL' if name in failed else 'PASS'}: Jenkins {name} image", flush=True)
    if failed:
        raise SystemExit("Infrastructure security gate failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
