resource "proxmox_virtual_environment_vm" "k3s" {
  for_each = local.k3s_nodes

  name        = each.key
  description = "K3s server node managed by Terraform"
  tags        = ["k3s", "kubernetes", "managed-by-terraform"]

  node_name = var.pm_node
  vm_id     = each.value.vm_id

  clone {
    vm_id = var.template_id
    full  = true
  }

  agent {
    enabled = var.qemu_agent_enabled

    wait_for_ip {
      disabled = !var.qemu_agent_enabled
      ipv4     = var.qemu_agent_enabled
    }
  }

  stop_on_destroy = true
  on_boot         = true

  cpu {
    cores = var.cpu_cores
    type  = var.cpu_type
  }

  memory {
    dedicated = var.memory_mb
  }

  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  initialization {
    datastore_id = var.cloud_init_datastore_id

    dns {
      servers = var.dns_servers
    }

    ip_config {
      ipv4 {
        address = each.value.ip
        gateway = var.gateway
      }
    }

    user_account {
      username = var.ssh_user
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_file)))]
    }
  }

  operating_system {
    type = "l26"
  }

  serial_device {}
}
