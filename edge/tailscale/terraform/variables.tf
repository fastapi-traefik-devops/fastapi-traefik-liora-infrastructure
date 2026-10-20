variable "pm_endpoint" {
  description = "Proxmox API URL, normally the private gateway from VM 200."
  type        = string
}

variable "pm_api_token" {
  description = "Proxmox API token in user@realm!tokenid=secret form."
  type        = string
  sensitive   = true
}

variable "pm_insecure" {
  description = "Allow the Proxmox host's self-signed TLS certificate."
  type        = bool
  default     = true
}

variable "pm_node" {
  description = "Actual Proxmox node name from pvesh get /nodes."
  type        = string
}

variable "template_id" {
  description = "Existing Debian 13 Cloud-Init template VM ID."
  type        = number
  default     = 9013
}

variable "cloud_init_datastore_id" {
  description = "Verified Proxmox VM disk storage from recovery/.env, also used for template 9013."
  type        = string
}

variable "router_vm_id" {
  description = "VM ID reserved for the Tailscale subnet router."
  type        = number
  default     = 250
}

variable "router_ip_cidr" {
  description = "Private address of the subnet router."
  type        = string
  default     = "192.168.77.250/24"
}

variable "bridge" {
  description = "Existing Proxmox private VNet bridge."
  type        = string
  default     = "vnet77"
}

variable "gateway" {
  description = "Private network gateway on the Proxmox host."
  type        = string
  default     = "192.168.77.1"
}

variable "ssh_public_key_file" {
  description = "Path from the Terraform directory to the administrator public key in recovery/."
  type        = string
  default     = "../../../recovery/LIORA-id_ed25519.pub"
}
