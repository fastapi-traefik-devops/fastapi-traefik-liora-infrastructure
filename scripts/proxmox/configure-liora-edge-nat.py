#!/usr/bin/env python3
"""Add only Liora HTTP/HTTPS forwarding to the existing project NAT table."""

import argparse
import datetime
import os
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--https', action='store_true', help='also publish HTTPS after certificate verification')
    parser.add_argument('--interface', default='vmbr0', help='public-facing Proxmox interface (default: vmbr0)')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run on the Proxmox host as root.')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]+', args.interface):
        raise SystemExit('Invalid public interface name.')
    path = Path('/etc/nftables.d/custom77-nat.nft')
    original = path.read_text()
    ports = [(80, 'HTTP'), (443, 'HTTPS')] if args.https else [(80, 'HTTP')]
    rules = [
        f'        iifname "{args.interface}" tcp dport {port} dnat to 192.168.77.240:{port} comment "Liora edge {name}"'
        for port, name in ports
    ]
    active = '\n'.join(line for line in original.splitlines() if not line.lstrip().startswith('#'))
    for (port, _), rule in zip(ports, rules):
        matches = [line.strip() for line in active.splitlines()
                   if re.search(r'\btcp dport\s+' + str(port) + r'\b', line)]
        if matches and matches != [rule.strip()]:
            raise SystemExit('Existing HTTP/HTTPS rule differs; inspect manually before changing it.')
    missing = [rule for rule in rules if rule.strip() not in active]
    if not missing:
        print('Liora forwarding rules already present; no changes made.')
        return
    # This helper accepts the existing single-chain table layout only. Refuse an
    # unfamiliar file rather than guessing insertion points or discarding rules.
    if not re.search(r'table ip custom77_nat\s*\{', active) or active.count('chain ') != 1:
        raise SystemExit('Unexpected NAT table layout; inspect manually.')
    ending = re.search(r'\n\s*}\s*\n\s*}\s*$', original)
    if not ending:
        raise SystemExit('Cannot identify prerouting chain end; no changes made.')
    candidate = original[:ending.start()] + '\n' + '\n'.join(missing) + original[ending.start():]
    backup = path.with_name(path.name + '.liora-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.bak')
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(candidate)
    try:
        subprocess.run(['nft', '-c', '-f', str(temp)], check=True)
        if path.read_text() != original:
            raise SystemExit('NAT file changed concurrently; no changes made.')
        backup.write_bytes(path.read_bytes())
        backup.chmod(path.stat().st_mode & 0o777)
        temp.chmod(path.stat().st_mode & 0o777)
        temp.replace(path)
        result = subprocess.run(['nft', '-f', str(path)])
        if result.returncode:
            path.write_text(original)
            subprocess.run(['nft', '-f', str(path)], check=True)
            raise SystemExit('NAT application failed; original file and table restored.')
        print('Added Liora forwarding for ports ' + ', '.join(str(port) for port, _ in ports)
              + '; existing rules preserved. Backup: ' + str(backup))
    finally:
        temp.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
