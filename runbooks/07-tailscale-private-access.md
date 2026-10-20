# Provision the Tailscale subnet router

**Where:** Management VM 200, from the repository checkout. The final VPN connectivity test runs on your PC/laptop. **Status:** The first live Terraform apply failed because the Cloud-Init datastore defaulted to unavailable `local-lvm`; the datastore correction awaits a live retest.

This phase clones Debian 13 template **9013** into VM **250** (`192.168.77.250/24`) on `vnet77`, then advertises `192.168.77.0/24` through Tailscale. Step 7 already placed the local, Git-ignored credentials in `recovery/` and [installed Ansible and Terraform](11-install-management-tools.md) on VM 200. Terraform reads the public key from that directory; Ansible uses its matching private key. The private key is never installed on VM 250.

## 1. Use the prepared recovery inputs

From the repository root on VM 200, load the prepared environment:

```bash
source recovery/.env
```

If you copied an example file or are unsure whether the local bundle is complete, optionally run `bash recovery/check_credentials.sh --tailscale`. It also makes a read-only Proxmox API request to verify that the token can read template 9013. Use `--offline` to skip that request before VM 200 has private API access. [Create or replace the token](12-create-proxmox-api-token.md) if needed. Run it without an argument to also check GHCR credentials and the Kubernetes recovery YAML. Keep the current Proxmox API endpoint and node name in `recovery/.env` so a replacement host needs only this one local update.

Before applying Terraform, confirm that VM ID **250** and `192.168.77.250` are free, or recover/reconcile the existing Terraform state if this is disaster recovery. Keep Terraform state in a restricted location.

Use the VM image storage selected and checked when [creating template 9013](03-create-debian13-template.md). Set its ID once as `DISK_STORAGE` in `recovery/.env`; that file exports `TF_VAR_cloud_init_datastore_id` from it for Terraform. The current host uses `vmdata`. On a replacement host, update this one value after the template storage preflight.

## 2. Create the router VM and one-use Tailscale key

### Terraform

The commands below use Terraform. If you installed OpenTofu, use `tofu` in place of `terraform`.

```bash
cd edge/tailscale/terraform
umask 077
terraform init
terraform fmt -check
terraform validate
terraform plan -out=router.tfplan
terraform show router.tfplan
```

Review the plan: a fresh install should add VM 250 and one Tailscale auth key, with no tailnet policy replacement. Confirm template **9013**, bridge `vnet77`, Proxmox node, router address, and `initialization.datastore_id` matching `DISK_STORAGE`. During disaster recovery, reconcile any existing VM and recovered state before applying. The generated auth key expires after one hour.

```sh
terraform apply router.tfplan
```

### Ansible

```bash
export TAILSCALE_AUTH_KEY="$(terraform output -raw ts_authkey)"
cd ../../..
ansible-playbook -i edge/tailscale/ansible/inventory.ini edge/tailscale/ansible/tailscale-router.yml --private-key recovery/LIORA-id_ed25519
unset TAILSCALE_AUTH_KEY
```

The auth key is passed to Ansible only for the router's first login. Terraform state contains the sensitive key, so protect and back it up with the other recovery state. If the one-use key expires before first login, review a replacement plan with `terraform plan -replace=tailscale_tailnet_key.router` and apply it before rerunning Ansible.
### Possible Problems
#### Resume after the `local-lvm` apply failure

If you failed with the error below, it means that `DISK_STORAGE='vmdata'` is wrong in `recovery/.env`. Probably you've missed the step in [03-create-debian13-template](03-create-debian13-template.md)

```sh
│ Error: All attempts fail:  
│ #1: the requested resource does not exist  
│ received an HTTP 500 response - Reason: storage 'local-lvm' does not exist  
│    
│   with proxmox_virtual_environment_vm.ts_router,  
│   on main.tf line 25, in resource "proxmox_virtual_environment_vm" "ts_router":  
│   25: resource "proxmox_virtual_environment_vm" "ts_router" {  
│    
```

The failed apply already created the Tailscale auth key. From `edge/tailscale/terraform`, check Terraform state and whether Proxmox left VM 250 behind:

```bash
terraform state list
ssh -i ../../../recovery/LIORA-id_ed25519 root@192.168.77.1 'qm status 250; qm config 250'
```

If VM 250 does **not** exist, load the updated configuration and create a **new** plan. If the existing one-use key is older than one hour, add `-replace=tailscale_tailnet_key.router` to the plan command before running it.

```bash
source ../../../recovery/.env
terraform plan -out=router.tfplan
terraform show router.tfplan
terraform apply router.tfplan
```

Do not reuse the earlier saved plan: Terraform state changed when the auth key was created. Review the new plan before applying, then continue with the auth key export and Ansible commands above. If VM 250 **does** exist, inspect its configuration and reconcile it with Terraform state before applying another plan; do not blindly create or delete it.

After successfule terraform run - go to **Ansible part**.
```sh
$ terraform apply router.tfplan  
proxmox_virtual_environment_vm.ts_router: Destroying... [id=250]  
proxmox_virtual_environment_vm.ts_router: Destruction complete after 1s  
proxmox_virtual_environment_vm.ts_router: Creating...  
proxmox_virtual_environment_vm.ts_router: Still creating... [00m10s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [00m20s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [00m30s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [00m40s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [00m50s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [01m00s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [01m10s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [01m20s elapsed]  
proxmox_virtual_environment_vm.ts_router: Still creating... [01m30s elapsed]  
proxmox_virtual_environment_vm.ts_router: Creation complete after 1m34s [id=250]  
  
Apply complete! Resources: 1 added, 0 changed, 1 destroyed.  
  
Outputs:  
  
ts_authkey = <sensitive>  
ts_router_ip = "192.168.77.250"
```

#### if Ansible fails

```sh
$ ansible-playbook -i edge/tailscale/ansible/inventory.ini 
....
....
ok: [ts-router]  
  
TASK [Register the subnet router on first login] ***********************************************************  
[ERROR]: Task failed: Module failed: non-zero return code  
Origin: /home/root-admin/fastapi-traefik-liora-infrastructure/edge/tailscale/ansible/tailscale-router.yml:68:7  
  
66       no_log: true  
67  
68     - name: Register the subnet router on first login  
        ^ column 7  
  
fatal: [ts-router]: FAILED! => {"censored": "the output has been hidden due to the fact that 'no_log: true' was specified for this result", "changed": true}  
  
PLAY RECAP **************************************************
ts-router                  : ok=10   changed=5    unreachable=0    failed=1    skipped=0    rescued=0    ignored=0
```
**an expired key is the most likely cause**. The first Terraform apply created a one-use key with a one-hour lifetime. The second apply replaced only VM 250, so it reused that earlier key. Ansible confirmed `TAILSCALE_AUTH_KEY` was nonempty, but `no_log: true` hides Tailscale’s exact error.

From `edge/tailscale/terraform` on VM 200, generate a fresh key:
```sh
terraform plan -replace=tailscale_tailnet_key.router -out=renew-key.tfplan
terraform show renew-key.tfplan
```

**Check that the plan replaces only the key, not VM 250**, then run:
```sh
terraform apply renew-key.tfplan
```
Then go again to the **Ansible** part.

## 3. Approve and verify private access

In the Tailscale admin console, approve `ts-router`'s advertised `192.168.77.0/24` route unless your existing policy auto-approves it. Confirm tailnet grants permit the intended administrators to use the route. This Terraform module does not manage tailnet policy.

![](<_resources/Pasted image 20261020173351.png>)

![](<_resources/Pasted image 20261020173856.png>)

![](<_resources/Pasted image 20261020173930.png>)

On VM 200, verify that Tailscale is running and IP forwarding is enabled on VM 250:

```bash
###cd ../../../
ssh -i recovery/LIORA-id_ed25519 root-admin@192.168.77.250 'sudo systemctl is-active tailscaled; sudo sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding; sudo tailscale status'
```

On your **PC/laptop**, connect to the same tailnet.
![](<_resources/Pasted image 20261020173634.png>)

A Linux client must enable subnet route acceptance with `sudo tailscale set --accept-routes`. Test access through the VPN:

```bash
ssh -i recovery/LIORA-id_ed25519 root-admin@192.168.77.200
ssh -i recovery/LIORA-id_ed25519 root@192.168.77.1
ssh -i recovery/LIORA-id_ed25519 root-admin@192.168.77.250
```

If your PC already has a direct route to `192.168.77.0/24`, inspect the selected route before treating SSH success as VPN proof. Record the live test result before marking this phase verified.
