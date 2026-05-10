# =============================================================================
# Compute module - instance + cloud-init bootstrap
# =============================================================================

resource "oci_core_instance" "plastic_detection_instance" {
  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  shape               = var.shape
  display_name        = var.display_name
  freeform_tags       = var.tags

  create_vnic_details {
    subnet_id        = var.subnet_id
    display_name     = "${var.display_name}-vnic"
    assign_public_ip = true
  }

  source_details {
    source_type = "image"
    source_id   = var.image_id
  }

  metadata = {
    ssh_authorized_keys = fileexists(var.ssh_public_key_path) ? file(var.ssh_public_key_path) : ""
    user_data = base64encode(templatefile("${path.module}/cloud-init.tpl", {
      docker_image = var.docker_image
    }))
  }

  timeouts {
    create = "60m"
  }
}
