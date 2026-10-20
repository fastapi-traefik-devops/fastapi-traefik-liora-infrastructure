# Create the private `vnet77` network

**Where:** Proxmox VE 9 web UI and host shell.

## Configure the VNet

- [ ] Keep the provider console open. In **Datacenter → SDN → Zones**, inspect existing zones. Create a **Simple** zone on a new host only if no suitable zone exists; `private` is an example name.
- [ ] In **Datacenter → SDN → VNets**, create `vnet77` in the selected zone only if it does not already exist. The template script uses `vnet77`; do not substitute `venet77`.
- [ ] Under `vnet77`, add `192.168.77.0/24` with gateway `192.168.77.1` and **SNAT enabled**. Use static addresses for the planned VMs. Check for an existing subnet first.
- [ ] Apply the configuration in **Datacenter → SDN**.

### If Proxmox reports a missing SDN include

> [!WARNING]
> Inspect `/etc/network/interfaces` for `source /etc/network/interfaces.d/sdn`. Adapt the host network configuration only after inspecting what is already there.

## Verify the network

- [ ] On Proxmox, check that `ip -br address show vnet77` includes `192.168.77.1/24` and `ip route` shows `192.168.77.0/24` on `vnet77`.
- [ ] After VM 200 exists, verify its gateway, DNS, and outbound connectivity from inside the VM.

**Done when:** `vnet77` exists, the gateway and route are present, and a VM on that VNet can reach its gateway and the internet. This network step does not publish any VM service to the public IP; the separate [nftables examples](../edge/nftables/README.md) cover the later VM 200 SSH DNAT step.
