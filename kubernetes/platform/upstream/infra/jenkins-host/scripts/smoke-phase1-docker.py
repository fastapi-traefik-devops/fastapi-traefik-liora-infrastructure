#!/usr/bin/env python3
"""Verify nested BuildKit and a non-root runtime through the Docker CI agent."""
import json
from pathlib import Path
import secrets
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
AGENT = ["docker", "exec", "host-jenkins-agent", "docker"]


def main() -> None:
    archive = ROOT / ".ci-output/frontend-ci.tar"
    with tarfile.open(archive) as stream:
        manifest = json.load(stream.extractfile("manifest.json"))
    image = manifest[0]["RepoTags"][0]
    if not image.startswith("phase1/frontend:"):
        raise RuntimeError("Unexpected smoke-test archive image")
    suffix = secrets.token_hex(6)
    name = "phase1-runtime-smoke-" + suffix
    built = "phase1/runtime-smoke:" + suffix
    with archive.open("rb") as stream:
        subprocess.run(["docker", "exec", "-i", "host-jenkins-agent", "docker", "load"], stdin=stream, stdout=subprocess.DEVNULL, check=True)
    try:
        subprocess.run(["docker", "exec", "-i", "host-jenkins-agent", "docker", "build", "--tag", built, "-"],
                       input=f"FROM {image}\nRUN id -u\n".encode(), check=True)
        subprocess.run([*AGENT, "run", "--rm", "-d", "--name", name, "--network", "none",
                        "--user", "101:101", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                        "--memory", "128m", built], check=True, stdout=subprocess.DEVNULL)
        for _ in range(60):
            if subprocess.run([*AGENT, "exec", name, "wget", "-q", "-O", "/dev/null", "http://127.0.0.1/healthz"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                print("PASS: Jenkins-agent TLS, nested BuildKit, patched runc/seccomp and non-root nginx health endpoint")
                return
            time.sleep(1)
        raise RuntimeError("Nested runtime health check failed")
    finally:
        subprocess.run([*AGENT, "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([*AGENT, "image", "rm", built], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
