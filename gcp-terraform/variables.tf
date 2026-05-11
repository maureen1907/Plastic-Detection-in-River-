# =============================================================================
# Input variables
# =============================================================================

# ---- GCP placement ---------------------------------------------------------

variable "project_id" {
  description = "GCP project ID (slug, not number)"
  type        = string
}

variable "region" {
  description = "GCP region. Sydney is the closest to Melbourne."
  type        = string
  default     = "australia-southeast1"
}

variable "zone" {
  description = "GCP zone within the region"
  type        = string
  default     = "australia-southeast1-a"
}

# ---- Cluster sizing --------------------------------------------------------

variable "machine_type" {
  description = "GCE machine type. Assignment requires 4 vCPU + 8 GB RAM."
  type        = string
  default     = "n1-custom-4-8192" # exactly 4 vCPU + 8 GB
}

variable "worker_count" {
  description = "Number of K8s worker nodes."
  type        = number
  default     = 2
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB. Image + container + model needs ~10 GB minimum."
  type        = number
  default     = 30
}

variable "boot_disk_image" {
  description = "GCE source image"
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

# ---- SSH access ------------------------------------------------------------

variable "ssh_user" {
  description = "Linux user to create with the supplied SSH public key"
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key (.pub) to authorise on all nodes"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

# ---- Application -----------------------------------------------------------

variable "docker_image" {
  description = "Docker image to deploy in the cluster"
  type        = string
  default     = "mpha0039/plastic-detection:v2"
}

# ---- Tagging ---------------------------------------------------------------

variable "labels" {
  description = "Labels applied to every resource for cost tracking."
  type        = map(string)
  default = {
    project     = "plastic-detection"
    environment = "dev"
    managed-by  = "terraform"
    unit        = "fit5225"
  }
}
