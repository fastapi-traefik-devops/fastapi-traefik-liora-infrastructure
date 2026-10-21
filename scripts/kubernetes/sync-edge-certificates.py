#!/usr/bin/env python3
"""Pull issued edge certificates privately and update namespace TLS Secrets."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    helper = Path(__file__).with_name('install-application-tls.py')
    # A fixed peer and fixed remote paths prevent credentials or shell input from
    # being interpolated into remote commands. Existing SSH trust is required.
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'ConnectTimeout=20', 'root-admin@192.168.77.240']
    with tempfile.TemporaryDirectory(prefix='liora-tls-sync-', dir=Path.home()) as directory:
        root = Path(directory)
        for env in ['dev', 'stage', 'prod']:
            files = {}
            for name in ['fullchain.pem', 'privkey.pem']:
                result = subprocess.run(
                    ssh + ['sudo -n cat /etc/letsencrypt/live/liora-' + env + '/' + name],
                    capture_output=True, check=False,
                )
                if result.returncode:
                    raise RuntimeError()
                path = root / (env + '-' + name)
                with open(path, 'xb', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
                    stream.write(result.stdout)
                files[name] = path
            result = subprocess.run([
                sys.executable, str(helper), env, '--certificate', str(files['fullchain.pem']),
                '--private-key', str(files['privkey.pem']),
            ], capture_output=True, check=False)
            if result.returncode:
                raise RuntimeError()
            print(env + ': issued edge certificate validated and synchronized; values withheld')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Certificate synchronization failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
