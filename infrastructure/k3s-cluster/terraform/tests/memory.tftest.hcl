mock_provider "proxmox" {}

variables {
  pm_endpoint             = "https://192.0.2.1:8006/"
  pm_node                 = "fixture-node"
  pm_api_token            = "fixture@pve!fixture=00000000-0000-0000-0000-000000000000"
  cloud_init_datastore_id = "fixture-storage"
  ssh_public_key_file     = "tests/fixtures/fake-admin.pub"
}

run "six_nodes_have_fixed_8gib" {
  command = plan

  assert {
    condition     = toset([for node in proxmox_virtual_environment_vm.k3s : node.vm_id]) == toset([201, 202, 203, 211, 212, 213])
    error_message = "The memory policy must cover all six NONPROD and PROD nodes."
  }

  assert {
    condition = alltrue([
      for node in proxmox_virtual_environment_vm.k3s :
      node.memory[0].dedicated == 8192 && node.memory[0].floating == 0
    ])
    error_message = "Every K3s node must have 8192 MiB dedicated RAM with ballooning disabled."
  }
}

run "reject_2gib_override" {
  command = plan

  variables {
    memory_mb = 2048
  }

  expect_failures = [var.memory_mb]
}
