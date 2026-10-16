#!/usr/bin/env python3
"""Migrate the dedicated Docker Jenkins to the Phase 1 Compose stack.

Only Jenkins containers and named volumes are touched. The pre-migration home
is archived privately before the old containers are stopped or renamed.
"""
from __future__ import annotations

import base64
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "infra/jenkins-host"
PRIVATE = ROOT / ".jenkins-host"
COMPOSE = ROOT / ".tools/phase1/docker-compose"
URL = "http://127.0.0.1:8085"


def run(*argv: str, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def compose(*argv: str):
    executable = str(COMPOSE) if COMPOSE.is_file() else "docker-compose"
    return run(executable, "-f", str(CONFIG / "docker-compose.yml"), *argv)


def inspect(name: str):
    result = subprocess.run(["docker", "container", "inspect", name], capture_output=True, text=True)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def secret_file(name: str, value: str | None = None) -> Path:
    path = PRIVATE / "secrets" / name
    if path.exists():
        if value is not None and path.read_text().strip() != value:
            path.write_text(value + "\n")
    else:
        if value is None:
            value = secrets.token_urlsafe(36)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(value + "\n")
    path.chmod(0o600)
    return path


def api(path: str) -> bytes:
    password = (PRIVATE / "secrets/jenkins-admin-password").read_text().strip()
    auth = base64.b64encode(("admin:" + password).encode()).decode()
    request = urllib.request.Request(URL + path, headers={"Authorization": "Basic " + auth})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def wait_controller() -> None:
    for _ in range(90):
        try:
            state = json.loads(api("/api/json?tree=mode,numExecutors"))
            if state.get("numExecutors") == 0:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Jenkins controller did not start with zero executors")


def no_running_builds() -> None:
    state = inspect("host-jenkins")
    if not state or not state["State"]["Running"]:
        return
    try:
        data = json.loads(api("/computer/api/json?tree=computer[executors[currentExecutable[url]],oneOffExecutors[currentExecutable[url]]]"))
    except Exception as exc:
        raise RuntimeError("Cannot verify Jenkins is idle; migration stopped") from exc
    for node in data.get("computer", []):
        for executor in [*node.get("executors", []), *node.get("oneOffExecutors", [])]:
            if executor.get("currentExecutable"):
                raise RuntimeError("Jenkins has a running build; migration stopped")


def archive_home() -> None:
    backup_dir = PRIVATE / "backups"
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    backup_dir.chmod(0o700)
    existing = sorted(backup_dir.glob("jenkins-home-pre-phase1-*.tar.gz"))
    if existing:
        print("Existing private pre-migration Jenkins home backup retained")
        return
    archive = backup_dir / f"jenkins-home-pre-phase1-{datetime.now(UTC):%Y%m%d%H%M%S}.tar.gz"
    descriptor = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            run("docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
                "--cap-add", "DAC_OVERRIDE", "--cap-add", "DAC_READ_SEARCH",
                "--user", "0:0", "--entrypoint", "tar",
                "-v", "host-jenkins-home:/home:ro", "phase1/jenkins-controller:local",
                "-C", "/home", "-czf", "-", ".", stdout=target)
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    print("Private Jenkins home backup created")


def stop_old_containers() -> None:
    for name in ("host-jenkins-agent", "host-jenkins-docker", "host-jenkins"):
        state = inspect(name)
        if state and state.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") != "phase1-jenkins" and state["State"]["Running"]:
            run("docker", "stop", name, stdout=subprocess.DEVNULL)


def retire_old_containers() -> None:
    for name in ("host-jenkins-agent", "host-jenkins-docker", "host-jenkins"):
        state = inspect(name)
        if not state or state.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") == "phase1-jenkins":
            continue
        old_name = name + "-pre-phase1"
        if inspect(old_name):
            raise RuntimeError(f"Retired container name already exists: {old_name}")
        run("docker", "rename", name, old_name)
    # After the private backup, remove active references to legacy plugins,
    # including any Kubernetes cloud plugin from the prior Jenkins home.
    marker = PRIVATE / "plugins-replaced"
    if not marker.exists():
        run("docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
            "--cap-add", "DAC_OVERRIDE",
            "--user", "0:0", "-v", "host-jenkins-home:/home",
            "--entrypoint", "sh", "phase1/jenkins-controller:local", "-ec",
            "if [ -d /home/plugins ]; then mv /home/plugins /home/plugins.pre-phase1; fi")
        marker.touch(mode=0o600)


def write_node_secrets() -> None:
    for node, file_name in (("host-ci", "agent-secret"), ("registry-publisher", "publisher-secret")):
        document = ET.fromstring(api(f"/computer/{node}/jenkins-agent.jnlp"))
        args = document.findall(".//argument")
        if not args or not args[0].text:
            raise RuntimeError(f"No inbound identity available for {node}")
        secret_file(file_name, args[0].text)


def wait_nodes() -> None:
    for node in ("host-ci", "registry-publisher"):
        for _ in range(60):
            try:
                data = json.loads(api(f"/computer/{node}/api/json?tree=offline,numExecutors"))
                if data.get("offline") is False and data.get("numExecutors") == 1:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError(f"Docker Jenkins agent {node} is not online")


def main() -> None:
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    (PRIVATE / "secrets").mkdir(mode=0o700, exist_ok=True)
    PRIVATE.chmod(0o700)
    (PRIVATE / "secrets").chmod(0o700)
    secret_file("jenkins-admin-password")
    compose("config", "--quiet")
    compose("build", "controller", "agent", "docker")
    run("python3", str(ROOT / "ci/audit_ci_images.py"))
    no_running_builds()
    if inspect("host-jenkins") and inspect("host-jenkins").get("Config", {}).get("Labels", {}).get("com.docker.compose.project") != "phase1-jenkins":
        stop_old_containers()
        archive_home()
    retire_old_containers()
    compose("up", "-d", "--no-deps", "controller", "docker")
    wait_controller()
    write_node_secrets()
    compose("up", "-d", "--no-deps", "agent", "publisher")
    wait_nodes()
    print("Phase 1 Jenkins online at http://127.0.0.1:8085/ with two Docker agents and zero controller executors")


if __name__ == "__main__":
    main()
