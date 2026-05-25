# =============================================================================
# Compute module - input variables
# =============================================================================

variable "compartment_id" {
  description = "Compartment OCID where the instance will be created"
  type        = string
}

variable "subnet_id" {
  description = "Subnet OCID where the instance's primary VNIC will live"
  type        = string
}

variable "availability_domain" {
  description = "Full availability-domain name (e.g. iSQa:AP-MELBOURNE-1-AD-1)"
  type        = string
}

variable "image_id" {
  description = "OCID of the Ubuntu image to boot from"
  type        = string
}

variable "shape" {
  description = "Instance shape"
  type        = string
  default     = "VM.Standard.E2.1.Micro"
}

variable "display_name" {
  description = "Display name for the instance"
  type        = string
  default     = "plastic-detection-api"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key (.pub) used to authorise instance access"
  type        = string
}

variable "docker_image" {
  description = "Docker image (registry/name:tag) to pull and run on first boot"
  type        = string
}

variable "tags" {
  description = "Freeform tags applied to the instance"
  type        = map(string)
  default     = {}
}
