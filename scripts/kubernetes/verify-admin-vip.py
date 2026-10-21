#!/usr/bin/env python3
"""Verify Admin VIP ownership, admission, Service status and optional node IPs."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', required=True, choices=['nonprod', 'prod'])
    parser.add_argument('--check-admission', action='store_true')
    parser.add_argument('--check-node-addresses', action='store_true')
    parser.add_argument('--known-hosts', type=Path)
    args = parser.parse_args()
    cluster = args.cluster
    vip = '192.168.77.16' if cluster == 'nonprod' else '192.168.77.17'
    node_ids = [201, 202, 203] if cluster == 'nonprod' else [211, 212, 213]
    kubeconfig = Path.home() / '.kube' / ('config-dev-stage' if cluster == 'nonprod' else 'config-prod')
    base = ['kubectl', '--kubeconfig=' + str(kubeconfig)]

    def get(arguments):
        result = subprocess.run(base + arguments + ['-o', 'json'], text=True, capture_output=True)
        assert result.returncode == 0
        return json.loads(result.stdout)

    lease = get(['-n', 'kube-system', 'get', 'lease', 'liora-admin-services'])
    leader = lease['spec']['holderIdentity']
    policy = get(['get', 'validatingadmissionpolicy', 'liora-admin-vip-status-owner'])
    assert not policy.get('status', {}).get('typeChecking', {}).get('expressionWarnings')
    daemons = get(['-n', 'kube-system', 'get', 'daemonsets'])['items']
    assert not any(d['metadata']['name'].startswith('svclb-') and
                   not d['metadata']['name'].startswith('svclb-traefik-') for d in daemons)
    services = get(['get', 'service', '-A', '-l', 'liora.aprt.info/access=private-admin'])['items']
    expected = ({('argocd', 'argocd-admin'): 8080, ('app-dev', 'adminer-private'): 8081,
                 ('app-stage', 'adminer-private'): 8082} if cluster == 'nonprod' else
                {('argocd', 'argocd-admin'): 8080, ('app-prod', 'adminer-private'): 8081})
    expected.update({('monitoring', 'grafana-admin'): 3000, ('monitoring', 'prometheus-admin'): 9090,
                     ('monitoring', 'alertmanager-admin'): 9093})
    actual = {(s['metadata']['namespace'], s['metadata']['name']): s for s in services}
    assert expected.keys() <= actual.keys()
    if ('jenkins', 'jenkins-admin') in actual:
        assert cluster == 'nonprod'
        expected[('jenkins', 'jenkins-admin')] = 8085
    assert actual.keys() == expected.keys()
    for key, port in expected.items():
        service = actual[key]
        assert service['spec']['loadBalancerClass'] == 'liora.aprt.info/admin-vip'
        assert service['spec']['allocateLoadBalancerNodePorts'] is False
        assert all('nodePort' not in entry for entry in service['spec']['ports'])
        assert [entry['port'] for entry in service['spec']['ports']] == [port]
        assert service['metadata']['annotations']['kube-vip.io/loadbalancerIPs'] == vip
        assert service['metadata']['annotations']['kube-vip.io/vipHost'] == leader
        assert [entry['ip'] for entry in service['status']['loadBalancer']['ingress']] == [vip]
        endpoints = get(['-n', key[0], 'get', 'endpointslice', '-l',
                         'kubernetes.io/service-name=' + key[1]])['items']
        assert any(endpoint.get('conditions', {}).get('ready')
                   for item in endpoints for endpoint in item.get('endpoints', []))
    summary = {'cluster': cluster, 'vip': vip, 'leader': leader, 'private_services': len(actual),
               'nodeports': 0, 'administrative_servicelb_daemonsets': 0}
    if args.check_admission:
        patch = json.dumps({'status': {'loadBalancer': {'ingress': [{'ip': vip}]}}})
        command = base + ['-n', 'monitoring', 'patch', 'service', 'prometheus-admin',
                          '--subresource=status', '--type=merge', '-p', patch, '--dry-run=server']
        rejected = subprocess.run(command, text=True, capture_output=True)
        assert rejected.returncode != 0
        assert 'Administrative LoadBalancer status belongs to kube-vip-admin' in rejected.stderr
        allowed = subprocess.run(command + ['--as=system:serviceaccount:kube-system:kube-vip-admin'],
                                 text=True, capture_output=True)
        assert allowed.returncode == 0
        summary['foreign_status_denied'] = True
        summary['owner_status_allowed'] = True
    if args.check_node_addresses:
        root = Path(__file__).resolve().parents[2]
        owners = []
        for node_id in node_ids:
            command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                       '-o', 'StrictHostKeyChecking=yes']
            if args.known_hosts:
                assert args.known_hosts.is_file()
                command += ['-o', 'UserKnownHostsFile=' + str(args.known_hosts)]
            command += ['-i', str(root / 'recovery/LIORA-id_ed25519'),
                        'root-admin@192.168.77.' + str(node_id), 'ip -j address show dev eth0']
            result = subprocess.run(command, text=True, capture_output=True)
            assert result.returncode == 0
            addresses = json.loads(result.stdout)
            if any(address['local'] == vip for item in addresses for address in item.get('addr_info', [])):
                owners.append(node_id)
        assert len(owners) == 1
        owner_node = get(['get', 'node', leader])
        assert any(address['type'] == 'InternalIP' and address['address'] == '192.168.77.' + str(owners[0])
                   for address in owner_node['status']['addresses'])
        summary['physical_vip_owners'] = owners
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({'verified': False, 'error_type': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
