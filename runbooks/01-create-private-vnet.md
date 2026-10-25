# Create the private `vnet77` network

**Where:** Proxmox VE 9 web UI and host shell.

## Configure the VNet

- [ ] Keep the provider console open. In **Datacenter → SDN → Zones**,
      inspect existing zones. If no suitable zone exists, create a
      **Simple** zone. `private` is an example name.
- [ ] In **Datacenter → SDN → VNets**, check for `vnet77`. If absent,
      create it in the selected zone. Use this exact VNet name.
- [ ] Under `vnet77`, add `192.168.77.0/24` with gateway `192.168.77.1` and **SNAT enabled**. Use static addresses for the planned VMs. Check for an existing subnet first.
- [ ] Apply the configuration in **Datacenter → SDN**.

### If Proxmox reports a missing SDN include

> [!WARNING]
> Inspect `/etc/network/interfaces` for `source /etc/network/interfaces.d/sdn`. Adapt the host network configuration only after inspecting what is already there.

## Verify the network

- [ ] On Proxmox, check that `ip -br address show vnet77` includes `192.168.77.1/24` and `ip route` shows `192.168.77.0/24` on `vnet77`.
- [ ] After VM 200 exists, verify its gateway, DNS, and outbound connectivity from inside the VM.

**Done when:** `vnet77` exists with gateway `192.168.77.1`, the route is
present, and a VM on the VNet can reach the gateway and Internet. The
[VM 200 SSH procedure](05-configure-vm200-ssh-dnat.md) configures public DNAT.
