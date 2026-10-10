# Ansible automation

The playbooks intentionally mirror the manual learning path rather than hiding the
VIP bootstrap inside a large role.

## Install Ansible dependency

```bash
ansible-galaxy collection install -r requirements.yml
```

## Configure inventory

```bash
cp inventory.yml.example inventory.yml
```

## Configure secret

```bash
cp group_vars/all/vault.yml.example group_vars/all/vault.yml
$EDITOR group_vars/all/vault.yml
ansible-vault encrypt group_vars/all/vault.yml
```

## Verify SSH

```bash
ansible all -i inventory.yml -m ping
```

## Run

```bash
ansible-playbook -i inventory.yml site.yml --ask-vault-pass
```

## Why not make the official `k3s-io/k3s-ansible` collection mandatory?

It is a good vanilla K3s project and supports automatic embedded-etcd HA with
multiple server hosts.

This repository has one additional bootstrapping requirement:

```text
first server
  ↓
install kube-vip
  ↓
join remaining servers through VIP
```

The small local playbooks make this order explicit and auditable.

The official project remains an excellent reference or replacement if you prefer
to bootstrap the cluster first and add the VIP afterward.
