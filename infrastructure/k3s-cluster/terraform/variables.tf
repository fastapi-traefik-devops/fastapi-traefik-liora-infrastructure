variable "pm_endpoint" {
  description = "Proxmox API URL, normally the private gateway from VM 200."
  type        = string
}

variable "pm_api_token" {
  description = "Proxmox API token supplied through TF_VAR_pm_api_token."
  type        = string
  sensitive   = true
}

variable "pm_insecure" {
  description = "Allow a self-signed Proxmox API certificate."
  type        = bool
  default     = true
}

variable "pm_node" {
  description = "Proxmox node that hosts both K3s clusters."
  type        = string
}

variable "template_id" {
  description = "Debian 13 Cloud-Init template VM ID."
  type        = number
  default     = 9013
}

variable "cloud_init_datastore_id" {
  description = "Verified Proxmox VM disk storage from recovery/.env, also used for template 9013."
  type        = string
}

variable "bridge" {
  description = "Proxmox bridge or SDN VNet connected to 192.168.77.0/24."
  type        = string
  default     = "vnet77"
}

variable "gateway" {
  type    = string
  default = "192.168.77.1"
}

variable "dns_servers" {
  type    = list(string)
  default = ["1.1.1.1", "1.0.0.1"]
}

variable "ssh_user" {
  type    = string
  default = "root-admin"
}

variable "ssh_public_key_file" {
  description = "Path from the Terraform directory to the administrator public key in recovery/."
  type        = string
  default     = "../../../recovery/LIORA-id_ed25519.pub"
}

variable "cpu_type" {
  description = "Use host for one-host performance; x86-64-v2-AES is more migration-friendly."
  type        = string
  default     = "x86-64-v2-AES"
}

variable "cpu_cores" {
  type    = number
  default = 2
}

variable "memory_mb" {
  description = "Maximum K3s VM memory in MiB."
  type        = number
  default     = 8192
}

variable "memory_min_mb" {
  description = "Minimum K3s VM memory in MiB with Proxmox ballooning."
  type        = number
  default     = 2048
}

variable "qemu_agent_enabled" {
  description = "Set true only after qemu-guest-agent exists and runs in the guests."
  type        = bool
  default     = false
}
