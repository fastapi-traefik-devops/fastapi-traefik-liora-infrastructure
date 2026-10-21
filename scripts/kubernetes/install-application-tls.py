#!/usr/bin/env python3
"""Validate a certificate/key pair and install only the selected app TLS Secret."""

import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives import serialization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=['dev', 'stage', 'prod'])
    parser.add_argument('--certificate', type=Path, required=True)
    parser.add_argument('--private-key', type=Path, required=True)
    args = parser.parse_args()
    host = 'liora.aprt.info' if args.environment == 'prod' else args.environment + '.liora.aprt.info'
    suffix = 'prod' if args.environment == 'prod' else 'dev-stage'
    kubeconfig = Path.home() / '.kube' / ('config-' + suffix)
    cert_text = args.certificate.read_text()
    key_text = args.private_key.read_text()
    if args.private_key.stat().st_mode & 0o077:
        raise ValueError('Private key permissions')
    cert = x509.load_pem_x509_certificate(cert_text.encode())
    key = serialization.load_pem_private_key(key_text.encode(), password=None)
    encoding = serialization.Encoding.DER
    fmt = serialization.PublicFormat.SubjectPublicKeyInfo
    assert cert.public_key().public_bytes(encoding, fmt) == key.public_key().public_bytes(encoding, fmt)
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    assert host in names  # Explicit per-host certificate, not wildcard guessing.
    if hasattr(cert, 'not_valid_before_utc'):
        before, after = cert.not_valid_before_utc, cert.not_valid_after_utc
    else:
        before = cert.not_valid_before.replace(tzinfo=datetime.timezone.utc)
        after = cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
    assert before <= datetime.datetime.now(datetime.timezone.utc) < after
    base = ['kubectl', '--kubeconfig=' + str(kubeconfig)]
    server = subprocess.check_output(base + ['config', 'view', '--minify', '-o',
                                            'jsonpath={.clusters[0].cluster.server}'], text=True)
    assert server == 'https://192.168.77.' + ('12' if suffix == 'prod' else '11') + ':6443'
    obj = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': 'app-tls', 'namespace': 'app-' + args.environment}, 'type': 'kubernetes.io/tls',
        'stringData': {'tls.crt': cert_text, 'tls.key': key_text}}
    result = subprocess.run(base + ['apply', '--server-side', '--field-manager=liora-tls', '-f', '-'],
                            input=json.dumps(obj), text=True, capture_output=True)
    assert result.returncode == 0
    print(args.environment + ': validated certificate/key and installed app-tls; values withheld')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Crypto/Kubernetes errors can include input; only report the type.
        print('TLS installation failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
