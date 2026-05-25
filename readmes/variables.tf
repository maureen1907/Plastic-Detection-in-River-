# =============================================================================
# Input variables
# =============================================================================

# ---- OCI authentication ----------------------------------------------------

variable "tenancy_ocid" {
  description = "OCI Tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "OCI User OCID"
  type        = string
}

variable "fingerprint" {
  description = "API Key Fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to private API key (.pem file)"
  type        = string
}

variable "region" {
  description = "OCI Region (e.g. ap-melbourne-1)"
  type        = string
}

# ---- Resource placement ----------------------------------------------------

variable "compartment_ocid" {
  description = "Compartment OCID for resources. Falls back to tenancy_ocid if empty."
  type        = string
  default     = ""
}

variable "availability_domain" {
  description = "Availability Domain index (1-based). ap-melbourne-1 only has 1 AD."
  type        = string
  default     = "1"

  validation {
    condition     = contains(["1", "2", "3"], var.availability_domain)
    error_message = "availability_domain must be \"1\", \"2\", or \"3\"."
  }
}

# ---- Compute ---------------------------------------------------------------

variable "shape" {
  description = "Instance shape. VM.Standard.E2.1.Micro is the AMD Always Free tier."
  type        = string
  default     = "VM.Standard.E2.1.Micro"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key (.pub file) used to authorise instance access"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

# ---- Application -----------------------------------------------------------

variable "docker_image" {
  description = "Docker image (registry/name:tag) for the plastic-detection API. Pulled and run by cloud-init on first boot."
  type        = string
  default     = "mpha0039/plastic-detection:latest"
}

# ---- Tagging ---------------------------------------------------------------

variable "tags" {
  description = "Freeform tags applied to every resource for cost tracking and ownership."
  type        = map(string)
  default = {
    Project     = "plastic-detection"
    Environment = "dev"
    ManagedBy   = "terraform"
    Unit        = "FIT5225"
  }
}
