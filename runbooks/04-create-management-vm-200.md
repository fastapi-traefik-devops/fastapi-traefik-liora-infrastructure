# Create management VM 200

**Where:** Proxmox VE 9 host. VM 200 is created directly on Proxmox.

## Preflight

- [ ] Verify that template `9013` exists, `vnet77` is active, and VM ID `200` is free.

### If VM 200 already exists

> [!WARNING]
> Inspect the existing VM. Do not clone another VM over it.

## Clone and configure VM 200

- [ ] On a new host, make a full clone: `qm clone 9013 200 --name k3s-mgmt --full`.
- [ ] Set the VM's Cloud-Init network and identity with a matching public-key file on the Proxmox host:

   ```bash
   qm set 200 --cores 2 --memory 2048
   qm set 200 --ipconfig0 ip=192.168.77.200/24,gw=192.168.77.1 --nameserver 1.1.1.1
   qm set 200 --ciuser root-admin --sshkeys /path/to/admin-key.pub
   qm cloudinit update 200
   ```

## Verify the management VM

- [ ] Check `qm config 200` and `qm cloudinit dump 200 user`; ensure only the public key is present.
- [ ] Start with `qm start 200`. In the Proxmox console, verify address `.200`, default route via `.1`, DNS, and outbound connectivity.
- [ ] Confirm SSH login as `root-admin` through an available trusted path. VM 200 is **not** a K3s node.

**Done when:** VM 200 is reachable at `192.168.77.200` with the intended SSH key.
