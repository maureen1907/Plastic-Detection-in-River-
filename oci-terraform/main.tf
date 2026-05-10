# =============================================================================
# OCI Infrastructure for Plastic Detection API
#
# Project layout:
#   main.tf       - root composition: data sources, locals, module calls
#   versions.tf   - terraform/provider version pins, provider config
#   variables.tf  - input variable declarations
#   outputs.tf    - output declarations
#   terraform.tfvars - actual values (gitignored)
#   modules/network/ - VCN, subnet, IGW, route table, security list
#   modules/compute/ - instance + cloud-init.tpl
# =============================================================================

# ---- Local values ----------------------------------------------------------

locals {
  # Use explicit compartment if provided, otherwise fall back to tenancy root.
  compartment_id = var.compartment_ocid != "" ? var.compartment_ocid : var.tenancy_ocid
}

# ---- Data sources (dynamic OCID lookups) -----------------------------------

data "oci_core_images" "ubuntu_images" {
  compartment_id           = local.compartment_id
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.shape
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# ---- Modules ---------------------------------------------------------------

module "network" {
  source = "./modules/network"

  compartment_id = local.compartment_id
  tags           = var.tags
}

module "compute" {
  source = "./modules/compute"

  compartment_id      = local.compartment_id
  subnet_id           = module.network.subnet_id
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[tonumber(var.availability_domain) - 1].name
  image_id            = data.oci_core_images.ubuntu_images.images[0].id
  shape               = var.shape
  ssh_public_key_path = var.ssh_public_key_path
  docker_image        = var.docker_image
  tags                = var.tags
}

# Note: state migration from the pre-module flat layout was performed via
# `terraform state mv` after the module refactor, since the OCI provider does
# not currently support `moved` blocks across resource type boundaries.
