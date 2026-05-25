# =============================================================================
# Network module - input variables
# =============================================================================

variable "compartment_id" {
  description = "Compartment OCID where networking resources will be created"
  type        = string
}

variable "vcn_cidr" {
  description = "CIDR block for the VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for the subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "name_prefix" {
  description = "Prefix used for display_name on every resource"
  type        = string
  default     = "plastic-detection"
}

variable "ingress_tcp_ports" {
  description = "List of TCP ports to allow inbound from 0.0.0.0/0"
  type        = list(number)
  default     = [22, 8000, 8501]
}

variable "tags" {
  description = "Freeform tags applied to every resource"
  type        = map(string)
  default     = {}
}
