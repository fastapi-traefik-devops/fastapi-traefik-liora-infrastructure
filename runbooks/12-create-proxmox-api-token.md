# Create and verify a Proxmox API token

**Where:** Connect from management VM 200 to the Proxmox host over SSH; test the API from VM 200. **Status:** Commands checked against Proxmox and provider documentation; token creation and permission scope still require a live test.

The Tailscale Terraform module reads `TF_VAR_pm_endpoint`, `TF_VAR_pm_node`, and `TF_VAR_pm_api_token` from the local, Git-ignored `recovery/.env`. Its token must be able to read template **9013**, clone/configure VM **250**, allocate VM disk space on the selected storage, and use `vnet77`.

## 1. Connect to Proxmox

From the repository root on VM 200:

```sh
ssh -i recovery/LIORA-id_ed25519 root@192.168.77.1
```

Choose one token setup below. The secret value is displayed **only when the token is created**. If the token ID already exists, inspect it with `pveum user token list <user>`; do not create a second token with the same ID.

### Simple root-owned token

Run on the Proxmox host:

```sh
pveum user token add root@pam mytoken --privsep 0
```

This token inherits `root@pam` permissions. Record the resulting secret as `TF_VAR_pm_api_token='root@pam!mytoken=<secret>'` in VM 200's `recovery/.env`. Use this option only when full Proxmox administration is intended for the automation token.

### Dedicated privilege-separated token

Run on the Proxmox host. This example limits VM administration to the VM tree and disk allocation to the current `vmdata` storage. Replace `vmdata` with the actual VM disk storage ID if the provider differs.

```sh
pveum user add api-user@pve
pveum acl modify / -user api-user@pve -role PVEAuditor
pveum acl modify /vms -user api-user@pve -role PVEVMAdmin
pveum acl modify /storage/vmdata -user api-user@pve -role PVEDatastoreAdmin
pveum acl modify /sdn/zones -user api-user@pve -role PVESDNUser
pveum user token add api-user@pve automation-token --privsep 1
pveum acl modify / -token 'api-user@pve!automation-token' -role PVEAuditor
pveum acl modify /vms -token 'api-user@pve!automation-token' -role PVEVMAdmin
pveum acl modify /storage/vmdata -token 'api-user@pve!automation-token' -role PVEDatastoreAdmin
pveum acl modify /sdn/zones -token 'api-user@pve!automation-token' -role PVESDNUser
pveum user permissions api-user@pve
pveum user token permissions api-user@pve automation-token
```

Record the resulting secret as `TF_VAR_pm_api_token='api-user@pve!automation-token=<secret>'` in VM 200's `recovery/.env`. The example `pveum acl modify / -token 'api-user@pve!automation-token' -role PVEVMAdmin` is syntactically valid, but **alone** it grants no effective privilege to a separated token whose owning user has none; `PVEVMAdmin` also does not supply storage allocation or SDN access. The VM, storage, and SDN grants above address those separate paths. Check the final effective permissions before running Terraform. [Proxmox user/token permissions](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc), [bpg Proxmox provider guidance](https://github.com/bpg/terraform-provider-proxmox/blob/main/docs/index.md).

## 2. Test the token from VM 200

Leave the Proxmox SSH session. From the repository root on VM 200, load `recovery/.env` and query the **9013 template configuration** through the private Proxmox API:

```sh
source recovery/.env
printf 'Authorization: PVEAPIToken=%s\n' "$TF_VAR_pm_api_token" | \
  curl -q --header @- --insecure --silent --show-error --connect-timeout 5 --max-time 15 \
    --output /dev/null --write-out 'HTTP %{http_code}\n' \
    "${TF_VAR_pm_endpoint%/}/api2/json/nodes/${TF_VAR_pm_node}/qemu/9013/config"
```

`HTTP 200` confirms that the token is accepted and can read template 9013. `401` indicates failed authentication; `403` indicates insufficient permissions; `404` indicates an incorrect node/template path or a resource hidden by permissions. The `--insecure` flag matches this repository's default for a self-signed Proxmox certificate; remove it when the host certificate is trusted. This read-only request cannot prove that VM cloning or disk allocation will succeed; the Terraform plan and live apply are the next checks.

The same read-only API probe runs in `bash recovery/check_credentials.sh --tailscale`. Add `--offline` to check only local files before VM 200 can reach the private API.

**Done when:** The token is stored in the ignored `recovery/.env`, its effective permissions match the intended scope, and the read-only API request returns `HTTP 200` from VM 200.
