# Create the private `vnet77` network

**Where:** Proxmox VE 9 web UI and host shell. **Status:** Draft compiled for this project's network; verify the provider-facing interface and current SDN state before applying changes to an existing host.

1. Keep the provider console open. In **Datacenter → SDN → Zones**, inspect existing zones. On a new host without a suitable zone, create a **Simple** zone (the existing notes use `private`). Do not replace a working zone merely to match that example name.
2. In **Datacenter → SDN → VNets**, inspect existing VNets. Create `vnet77` in the selected Simple zone only if it does not already exist. The supplied template screenshot and the checked-in template script use `vnet77`; the spoken name `venet77` must not be silently substituted in commands.
3. Under `vnet77`, add subnet `192.168.77.0/24` with gateway `192.168.77.1` and **SNAT enabled**. Use static addresses for the planned VMs. Check for an existing subnet before adding a duplicate.
4. Apply the SDN configuration in **Datacenter → SDN**. If Proxmox reports a missing SDN include, check whether `/etc/network/interfaces` contains `source /etc/network/interfaces.d/sdn`; adapt only after inspecting the host's current network configuration.
5. On the host, verify `ip -br address show vnet77` includes `192.168.77.1/24` and `ip route` contains `192.168.77.0/24` on `vnet77`. After VM 200 exists, verify its gateway, DNS, and outbound connectivity from inside the VM.

**Done when:** `vnet77` exists, the gateway and route are present, and a VM on that VNet can reach its gateway and the internet. This network step does not publish any VM service to the public IP.
