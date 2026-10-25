# Create and verify a Proxmox API token

**Where:** Connect from management VM 200 to the Proxmox host over SSH; test the API from VM 200.

The Tailscale and K3s Terraform modules read `TF_VAR_pm_endpoint`,
`TF_VAR_pm_node`, and `TF_VAR_pm_api_token` from ignored
`recovery/.env`. The token needs access to template **9013**, VM IDs
**250**, **201–203**, and **211–213**, the selected VM storage, and
`vnet77`.

## Connect to Proxmox

From the repository root on VM 200:

- [ ] Open a Proxmox host session:

```sh
ssh -i recovery/LIORA-id_ed25519 root@192.168.77.1
```

Choose one token setup below. The secret value is displayed **only when the token is created**.

### If the token ID already exists

> [!NOTE]
> Inspect it with `pveum user token list <user>`. Do not create a second token with the same ID.

## Create one token

### Simple root-owned token

Run on the Proxmox host:

- [ ] Create the root-owned token:

```sh
pveum user token add root@pam mytoken --privsep 0
```

This token inherits `root@pam` permissions. Record the secret as
`TF_VAR_pm_api_token='root@pam!mytoken=<secret>'` in VM 200's
`recovery/.env`. Use this option only if automation needs full
Proxmox administration.

### Dedicated privilege-separated token

Run on the Proxmox host. Use the storage ID selected for template 9013.
The commands grant VM administration, VM disk allocation, and VNet use.

#### Create the dedicated token and ACLs

- [ ] Create the dedicated user and privilege-separated token, then inspect effective permissions:

```sh
read -r -p 'VM disk storage ID used for template 9013: ' selected_storage
[[ "$selected_storage" =~ ^[A-Za-z][A-Za-z0-9_.-]*[A-Za-z0-9]$ ]] || { echo 'Invalid storage ID' >&2; exit 1; }
pvesm status --storage "$selected_storage" || exit 1
pveum user add api-user@pve
pveum acl modify / -user api-user@pve -role PVEAuditor
pveum acl modify /vms -user api-user@pve -role PVEVMAdmin
pveum acl modify "/storage/$selected_storage" -user api-user@pve -role PVEDatastoreAdmin
pveum acl modify /sdn/zones -user api-user@pve -role PVESDNUser
pveum user token add api-user@pve automation-token --privsep 1
pveum acl modify / -token 'api-user@pve!automation-token' -role PVEAuditor
pveum acl modify /vms -token 'api-user@pve!automation-token' -role PVEVMAdmin
pveum acl modify "/storage/$selected_storage" -token 'api-user@pve!automation-token' -role PVEDatastoreAdmin
pveum acl modify /sdn/zones -token 'api-user@pve!automation-token' -role PVESDNUser
pveum user permissions api-user@pve
pveum user token permissions api-user@pve automation-token
```

Record the secret as
`TF_VAR_pm_api_token='api-user@pve!automation-token=<secret>'`
in VM 200's `recovery/.env`. Check effective user and token permissions
before Terraform. A separated token cannot exceed its owner's permissions.
The ACLs above grant VM, storage, and SDN access separately.
See [Proxmox permissions](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc)
and [provider guidance](https://github.com/bpg/terraform-provider-proxmox/blob/main/docs/index.md).

## Test the token from VM 200

Leave the Proxmox SSH session. From the repository root on VM 200, load `recovery/.env` and query the **9013 template configuration** through the private Proxmox API:

- [ ] Send the read-only API request and confirm `HTTP 200`:

```sh
source recovery/.env
printf 'Authorization: PVEAPIToken=%s\n' "$TF_VAR_pm_api_token" | \
  curl -q --header @- --insecure --silent --show-error --connect-timeout 5 --max-time 15 \
    --output /dev/null --write-out 'HTTP %{http_code}\n' \
    "${TF_VAR_pm_endpoint%/}/api2/json/nodes/${TF_VAR_pm_node}/qemu/9013/config"
```

`HTTP 200` confirms that the token can read template 9013. The
`--insecure` flag permits the host's self-signed certificate. Remove
the flag when the certificate is trusted. Terraform checks VM clone and
disk allocation permissions during apply.

### If the API request does not return `HTTP 200`

> [!WARNING]
> `401` indicates failed authentication; `403` indicates insufficient permissions; `404` indicates an incorrect node/template path or a resource hidden by permissions. Correct the token or endpoint before using Terraform.

The same read-only API probe runs in `bash recovery/check_credentials.sh --tailscale`. Add `--offline` to check only local files before VM 200 can reach the private API.

**Done when:** The token is stored in the ignored `recovery/.env`, its effective permissions match the intended scope, and the read-only API request returns `HTTP 200` from VM 200.
