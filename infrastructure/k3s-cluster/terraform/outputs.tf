output "k3s_nodes" {
  value = {
    for name, vm in local.k3s_nodes :
    name => {
      vm_id = vm.vm_id
      ip    = split("/", vm.ip)[0]
    }
  }
}

output "next_step" {
  value = "Run Ansible separately with the dev/stage and prod inventories after SSH is ready on all six VMs."
}
