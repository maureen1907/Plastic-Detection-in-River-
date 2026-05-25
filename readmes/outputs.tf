# =============================================================================
# Root outputs
# =============================================================================

output "instance_public_ip" {
  description = "Public IP of the plastic-detection compute instance"
  value       = module.compute.public_ip
}

output "instance_id" {
  description = "OCID of the plastic-detection compute instance"
  value       = module.compute.instance_id
}

output "vcn_id" {
  description = "OCID of the VCN"
  value       = module.network.vcn_id
}

output "api_url" {
  description = "URL where the plastic-detection API will be reachable once cloud-init completes"
  value       = "http://${module.compute.public_ip}:8000"
}

output "ssh_command" {
  description = "Convenience command to SSH into the instance"
  value       = "ssh -i ~/.ssh/id_ed25519 ubuntu@${module.compute.public_ip}"
}
