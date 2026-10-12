#!/usr/bin/env python3
"""Build pinned infrastructure tools with patched Go dependencies, not app code."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

lock = json.loads(Path(__file__).with_name("tools.lock.json").read_text())
destination = Path("/out")
destination.mkdir(exist_ok=True)
for name in sys.argv[1:]:
    item = lock[name]
    with urllib.request.urlopen(item["source_url"], timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item["source_sha256"]:
        raise SystemExit("Source checksum mismatch: " + name)
    with tempfile.TemporaryDirectory(prefix="tool-source-") as temporary:
        directory = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            archive.extractall(directory, filter="data")
        source = next(path for path in directory.iterdir() if path.is_dir())
        environment = dict(os.environ, GOTOOLCHAIN="local", GOMAXPROCS="2", GOMEMLIMIT="1200MiB", CGO_ENABLED="1" if item.get("cgo") else "0")
        patches = [f"{package}@{version}" for package, version in item["go_patches"].items()]
        subprocess.run(["go", "get", *patches], cwd=source, env=environment, check=True)
        arguments = ["go", "build", "-mod=mod", "-p", "2", "-trimpath"]
        if item.get("cgo"):
            arguments += ["-tags", "seccomp", "-ldflags", "-linkmode external -extldflags -static"]
        arguments += ["-o", str(destination / name), item["build_package"]]
        subprocess.run(arguments, cwd=source, env=environment, check=True)
        provenance = destination / "provenance" / name
        provenance.mkdir(parents=True, exist_ok=True)
        for file_name in ("go.mod", "go.sum"):
            (provenance / file_name).write_bytes((source / file_name).read_bytes())
    print("Built checksum-verified infrastructure tool:", name, item["version"], flush=True)
