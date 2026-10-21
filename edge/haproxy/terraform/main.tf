terraform {
  required_version = ">= 1.8.0"
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.111.1"
    }
  }
}

provider "proxmox" {
  endpoint  = var.pm_endpoint
  api_token = var.pm_api_token
  insecure  = true
}

variable "pm_endpoint" { type = string }
variable "pm_node" { type = string }
variable "pm_api_token" {
  type      = string
  sensitive = true
}
variable "cloud_init_datastore_id" { type = string }
variable "ssh_public_key_file" {
  type    = string
  default = "../../../recovery/LIORA-id_ed25519.pub"
}

resource "proxmox_virtual_environment_vm" "edge" {
  name        = "liora-edge"
  description = "Liora application ingress edge; managed by Terraform"
  tags        = ["liora", "edge", "managed-by-terraform"]
  node_name   = var.pm_node
  vm_id       = 240
  on_boot     = true
  clone {
    vm_id = 9013
    full  = true
  }
  cpu {
    cores = 1
    type  = "x86-64-v2-AES"
  }
  memory { dedicated = 1024 }
  agent {
    enabled = false
    wait_for_ip { disabled = true }
  }
  network_device {
    bridge = "vnet77"
    model  = "virtio"
  }
  initialization {
    datastore_id = var.cloud_init_datastore_id
    dns { servers = ["1.1.1.1", "1.0.0.1"] }
    ip_config {
      ipv4 {
        address = "192.168.77.240/24"
        gateway = "192.168.77.1"
      }
    }
    user_account {
      username = "root-admin"
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_file)))]
    }
  }
  operating_system { type = "l26" }
  serial_device {}
  lifecycle { prevent_destroy = true }
}

output "edge_ipv4" { value = "192.168.77.240" }
