# =============================================================================
# Network module - outputs
# =============================================================================

output "vcn_id" {
  description = "OCID of the VCN"
  value       = oci_core_vcn.plastic_detection_vcn.id
}

output "subnet_id" {
  description = "OCID of the public subnet"
  value       = oci_core_subnet.plastic_detection_subnet.id
}
