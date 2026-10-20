provider "proxmox" {
  endpoint  = var.pm_endpoint
  api_token = var.pm_api_token
  insecure  = var.pm_insecure
}
