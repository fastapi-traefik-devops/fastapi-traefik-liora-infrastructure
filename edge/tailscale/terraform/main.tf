terraform {
  required_version = ">= 1.8.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.111.1"
    }
    tailscale = {
      source  = "tailscale/tailscale"
      version = "0.29.2"
    }
  }
}

provider "proxmox" {
  endpoint  = var.pm_endpoint
  api_token = var.pm_api_token
  insecure  = var.pm_insecure
}

# TAILSCALE_API_KEY and TAILSCALE_TAILNET come from the operator environment.
provider "tailscale" {}

resource "proxmox_virtual_environment_vm" "ts_router" {
  name      = "ts-router"
  node_name = var.pm_node
  vm_id     = var.router_vm_id

  clone {
    vm_id = var.template_id
    full  = true
  }

  cpu {
    cores = 1
  }

  memory {
    dedicated = 1024
  }

  agent {
    enabled = false
    wait_for_ip {
      disabled = true
    }
  }

  on_boot         = true
  stop_on_destroy = true

  network_device {
    bridge = var.bridge
    model  = "virtio"
  }

  initialization {
    datastore_id = var.cloud_init_datastore_id

    dns {
      servers = ["1.1.1.1"]
    }

    ip_config {
      ipv4 {
        address = var.router_ip_cidr
        gateway = var.gateway
      }
    }

    user_account {
      username = "root-admin"
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_file)))]
    }
  }

  operating_system {
    type = "l26"
  }

  serial_device {}
}

# This one-use key is stored in sensitive Terraform state until state is removed.
# Tailnet access policy and route approval are managed separately.
resource "tailscale_tailnet_key" "router" {
  reusable      = false
  ephemeral     = false
  preauthorized = true
  expiry        = 3600
  description   = "Tailscale router VM 250"
}
