#!/usr/bin/env python3
"""Install only the two pinned manifest validators; no security tools or scans."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
lock = json.loads(Path(__file__).with_name('tools.lock.json').read_text())
for name, item in lock.items():
    with urllib.request.urlopen(item['url'], timeout=60) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != item['sha256']:
        raise SystemExit('Validation tool checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        member = tar.getmember(name)
        if not member.isfile():
            raise SystemExit('Invalid validation executable')
        target = output / name
        target.write_bytes(tar.extractfile(member).read())
        target.chmod(0o755)
    print('Installed validator:', name, item['version'])
