#!/usr/bin/env python3
"""Install release binaries after verifying the checked-in SHA256 lock."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

for name, item in json.loads(Path(__file__).with_name("tools.lock.json").read_text()).items():
    if item.get("source_url"):
        continue
    with urllib.request.urlopen(item["url"], timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit("Checksum mismatch for " + name)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = next(x for x in archive.getmembers() if x.isfile() and Path(x.name).name == name)
        target = Path("/usr/local/bin") / name
        target.write_bytes(archive.extractfile(member).read())
        target.chmod(0o755)
    print("Verified pinned tool:", name, item["version"])
