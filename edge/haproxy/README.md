# Liora application edge

VM 240 (`liora-edge`, `192.168.77.240`) runs HAProxy independently of the
management VM and both Kubernetes API VIPs. Terraform clones template 9013 with
one vCPU and 1GiB RAM; the inherited 200GiB thin ZFS disk is retained. The VM
has `prevent_destroy` enabled. Terraform state is local operator data, never Git.

The existing K3s ServiceLB exposes Traefik on each cluster's three node addresses.
HAProxy balances TLS connections over `.201`–`.203` for DEV/STAGE and
`.211`–`.213` for PROD. These disjoint ingress endpoint sets are different from
API VIPs `.11`/`.12`. This increment keeps ServiceLB and does not introduce a
second address announcer. Dedicated floating ingress VIPs remain a later option.

The nonprod TLS routes are controlled by `liora_tls_nonprod_enabled`; enable
them only after both nonprod certificates and HTTPS ingress are verified.

TLS passes through HAProxy to namespace-local `app-tls` Secrets. Only the three
application SNI names are routed. Public port 80 accepts only those Host names,
redirects requests to HTTPS. Public certificates are issued and renewed by
cert-manager through Cloudflare DNS-01 inside each cluster. Argo CD and Adminer have no route through this configuration.

## Provision and configure

Run the Terraform module on the management VM with the same protected
`TF_VAR_pm_endpoint`, `TF_VAR_pm_node`, `TF_VAR_pm_api_token` and
`TF_VAR_cloud_init_datastore_id` used for cluster provisioning. Supply the
operator's public-key path through `TF_VAR_ssh_public_key_file`. Never put the
token in a command argument, tracked tfvars or shell tracing output.

```sh
terraform -chdir=edge/haproxy/terraform init
terraform -chdir=edge/haproxy/terraform plan -out=edge.tfplan
terraform -chdir=edge/haproxy/terraform apply edge.tfplan
ansible-playbook -i edge/haproxy/ansible/inventory.yml edge/haproxy/ansible/site.yml
```

Inspect the plan first: only VM 240 should be created. Confirm the VM ID and
address are unused. Use a private SSH identity/agent authorized on the new VM.
The playbook validates HAProxy before replacing its configuration and only
reloads on change. HAProxy does not load certificate private keys; each
environment's TLS Secret remains in its Kubernetes namespace.

For this live phase, the module, ignored state and plan reside on VM 200 at
`/home/root-admin/liora-phase7-edge/terraform`. The tracked module is the source
of truth; keep that local state with the operator's recovery archive. The live
state must be retained even if the Git checkout changes.

Certificate issuance and renewal are independent of VM 200 and VM 240.
Use [runbook 15](../../runbooks/15-publish-application.md) to provision the private
Cloudflare DNS token and independent per-cluster issuer, verify namespace-local
certificates and test renewal. Do not install the legacy distribution units.
Retained Certbot state and synchronization scripts are historical rollback
artifacts; see [Phase 11](../../docs/testreports/PHASE11_REPORT.md).
