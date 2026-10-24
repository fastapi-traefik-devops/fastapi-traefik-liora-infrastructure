#!/usr/bin/env python3
"""Verify the exact TLS certificate served by all application ingress endpoints."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=['dev', 'stage', 'prod'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--public', action='store_true', help='Also connect through public DNS; requires a working public network path')
    args = parser.parse_args()
    env = args.environment
    hostname = 'liora.aprt.info' if env == 'prod' else env + '.liora.aprt.info'
    config = Path.home() / '.kube' / ('config-prod' if env == 'prod' else 'config-dev-stage')
    base = ['kubectl', '--kubeconfig=' + str(config), '--request-timeout=30s', '-n', 'app-' + env]
    result = {'environment': env, 'hostname': hostname, 'verified': False, 'endpoints': []}
    try:
        command = subprocess.run(base + ['get', 'certificate', 'app-tls', '-o', 'json'],
                                 capture_output=True, timeout=45, check=True)
        certificate = json.loads(command.stdout)
        if not any(x['type'] == 'Ready' and x['status'] == 'True' for x in certificate.get('status', {}).get('conditions', [])):
            raise ValueError('Certificate is not Ready')
        if certificate['spec']['issuerRef']['name'] != 'letsencrypt-cloudflare':
            raise ValueError('Unexpected certificate issuer')
        result['revision'] = certificate['status']['revision']
        result['renewal_time'] = certificate['status']['renewalTime']
        command = subprocess.run(base + ['get', 'secret', 'app-tls', '-o', 'json'],
                                 capture_output=True, timeout=45, check=True)
        secret = json.loads(command.stdout)
        if secret['metadata'].get('annotations', {}).get('cert-manager.io/issuer-name') != 'letsencrypt-cloudflare':
            raise ValueError('TLS Secret has not been issued by the expected issuer')
        cert = x509.load_pem_x509_certificate(base64.b64decode(secret['data']['tls.crt']))
        expected = hashlib.sha256(cert.public_bytes(Encoding.DER)).hexdigest()
        result.update(serial=format(cert.serial_number, 'x'), fingerprint_sha256=expected,
                      expires=cert.not_valid_after_utc.isoformat())
        context = ssl.create_default_context()
        nodes = range(211, 214) if env == 'prod' else range(201, 204)
        addresses = [*[f'192.168.77.{node}' for node in nodes], '192.168.77.240']
        if args.public:
            addresses.append(hostname)
        result['public_dns_path_tested'] = args.public
        for address in addresses:
            with socket.create_connection((address, 443), timeout=20) as connection:
                with context.wrap_socket(connection, server_hostname=hostname) as secured:
                    actual = hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest()
                    if actual != expected:
                        raise ValueError('Served certificate differs from app-tls')
            result['endpoints'].append({'address': address, 'trusted_and_matches_secret': True})
        result['verified'] = True
    except Exception as error:
        result['error_type'] = type(error).__name__
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    sys.exit(main())
