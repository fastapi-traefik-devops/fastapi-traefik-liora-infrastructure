output "ts_authkey" {
  description = "One-use Tailscale auth key for the first router login."
  value       = tailscale_tailnet_key.router.key
  sensitive   = true
}

output "ts_router_ip" {
  description = "Private IPv4 address of the router VM."
  value       = split("/", var.router_ip_cidr)[0]
}
