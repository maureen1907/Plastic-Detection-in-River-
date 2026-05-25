# =============================================================================
# Compute module - outputs
# =============================================================================

output "instance_id" {
  description = "OCID of the compute instance"
  value       = oci_core_instance.plastic_detection_instance.id
}

output "public_ip" {
  description = "Public IP of the compute instance"
  value       = oci_core_instance.plastic_detection_instance.public_ip
}
