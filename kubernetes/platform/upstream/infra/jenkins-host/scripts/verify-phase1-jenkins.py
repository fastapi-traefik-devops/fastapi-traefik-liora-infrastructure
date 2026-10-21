#!/usr/bin/env python3
"""Read-only live checks for the Docker-only Phase 1 Jenkins architecture."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("phase1_bootstrap", ROOT / "infra/jenkins-host/scripts/bootstrap-phase1-jenkins.py")
bootstrap = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(bootstrap)


def api(path: str):
    return json.loads(bootstrap.api(path))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    state = api("/api/json?tree=numExecutors,mode,clouds[name]")
    check(state.get("numExecutors") == 0 and not state.get("clouds"), "Controller executors or cloud agents enabled")
    for name, label in (("host-ci", "host-ci"), ("registry-publisher", "registry-publisher")):
        node = api(f"/computer/{name}/api/json?tree=offline,numExecutors,assignedLabels[name]")
        check(node.get("offline") is False and node.get("numExecutors") == 1, f"Docker agent {name} unavailable")
        check(any(x["name"] == label for x in node.get("assignedLabels", [])), f"Agent label {label} missing")
    for name in ("host-jenkins", "host-jenkins-docker", "host-jenkins-agent", "host-jenkins-publisher"):
        container = bootstrap.inspect(name)
        check(bool(container and container["State"]["Running"]), f"Container {name} unavailable")
        check(container["Config"]["Labels"].get("com.docker.compose.project") == "phase1-jenkins", f"Container {name} not Compose managed")
    controller = bootstrap.inspect("host-jenkins")
    publisher = bootstrap.inspect("host-jenkins-publisher")
    build_agent = bootstrap.inspect("host-jenkins-agent")
    check(controller["Config"]["User"] == "1000:1000", "Controller runs as root")
    check(publisher["Config"]["User"] == "1000:1000", "Publisher runs as root")
    check(build_agent["Config"]["User"] == "1000:1000", "CI agent runs as root")
    check("phase1-jenkins_build" not in publisher["NetworkSettings"]["Networks"], "Publisher can reach Docker build network")
    check(not any(x.startswith(("DOCKER_HOST=", "DOCKER_CERT_PATH=")) for x in publisher["Config"]["Env"]), "Publisher has Docker access")
    mounts = [mount["Destination"] for mount in controller["Mounts"]]
    check("/var/jenkins_home" in mounts, "Persistent Jenkins home missing")
    for name in ("jenkins-admin-password", "agent-secret", "publisher-secret"):
        path = ROOT / ".jenkins-host/secrets" / name
        check(path.is_file() and stat.S_IMODE(path.stat().st_mode) == 0o600, f"Private file {name} missing or not mode 0600")
    for job in ("/job/app-ci/job/main", "/job/trusted/job/publish"):
        check(api(job + "/api/json?tree=buildable").get("buildable") is True, f"CI job {job} is disabled")
    plugins = api("/pluginManager/api/json?tree=plugins[shortName,active]")["plugins"]
    check(not any(p["shortName"] == "kubernetes" and p["active"] for p in plugins), "Kubernetes plugin remains active")
    subprocess.run(["docker", "exec", "host-jenkins-agent", "docker", "version", "--format", "{{.Server.Version}}"], check=True)
    print("PASS: Docker controller and both Docker agents; persistent home; no cloud agent; publisher isolated; both CI jobs enabled")


if __name__ == "__main__":
    main()
