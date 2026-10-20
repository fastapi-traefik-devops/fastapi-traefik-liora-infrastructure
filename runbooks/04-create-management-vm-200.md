# Create management VM 200

**Where:** Proxmox VE 9 host. **Status:** The existing VM 200 was created manually; this runbook formalizes that layout and has not been replayed on a replacement host.

1. Verify that template `9013` exists, `vnet77` is active, and VM ID `200` is free. If VM 200 already exists, inspect it and **do not clone another VM over it**.
2. On a new host, make a full clone: `qm clone 9013 200 --name k3s-mgmt --full`.
3. Set the VM's Cloud-Init network and identity, using a verified public-key file on the Proxmox host:

   ```bash
   qm set 200 --cores 2 --memory 2048
   qm set 200 --ipconfig0 ip=192.168.77.200/24,gw=192.168.77.1 --nameserver 1.1.1.1
   qm set 200 --ciuser root-admin --sshkeys /path/to/admin-key.pub
   qm cloudinit update 200
   ```

4. Check `qm config 200` and `qm cloudinit dump 200 user`; ensure only the public key is present. Start with `qm start 200`. Via the Proxmox console, verify the VM has address `.200`, default route via `.1`, DNS, and outbound connectivity.
5. Confirm SSH login as `root-admin` through an available trusted path. VM 200 is **not** a K3s node.
6. **Recovery only:** Before any Terraform apply, compare the restored state with the actual VM 200. Import or reconcile it in the chosen state strategy; do not allow a plan to create a duplicate VM or replace its disk.

**Done when:** VM 200 is reachable at `192.168.77.200` with the intended SSH key and the state reconciliation requirement is recorded for recovery.
