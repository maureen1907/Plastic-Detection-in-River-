# =============================================================================
# Network module - VCN, internet gateway, route table, security list, subnet
# =============================================================================

resource "oci_core_vcn" "plastic_detection_vcn" {
  compartment_id = var.compartment_id
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.name_prefix}-vcn"
  dns_label      = "plasticdet"
  freeform_tags  = var.tags
}

resource "oci_core_internet_gateway" "plastic_detection_ig" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.plastic_detection_vcn.id
  display_name   = "${var.name_prefix}-ig"
  enabled        = true
  freeform_tags  = var.tags
}

resource "oci_core_route_table" "plastic_detection_rt" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.plastic_detection_vcn.id
  display_name   = "${var.name_prefix}-rt"
  freeform_tags  = var.tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.plastic_detection_ig.id
  }
}

resource "oci_core_security_list" "plastic_detection_sl" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.plastic_detection_vcn.id
  display_name   = "${var.name_prefix}-sl"
  freeform_tags  = var.tags

  # One ingress rule per allowed port. Generated dynamically from var.ingress_tcp_ports
  # so adding/removing ports is a one-line change.
  dynamic "ingress_security_rules" {
    for_each = var.ingress_tcp_ports
    content {
      protocol = "6" # TCP
      source   = "0.0.0.0/0"
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  egress_security_rules {
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
  }
}

resource "oci_core_subnet" "plastic_detection_subnet" {
  compartment_id    = var.compartment_id
  vcn_id            = oci_core_vcn.plastic_detection_vcn.id
  cidr_block        = var.subnet_cidr
  display_name      = "${var.name_prefix}-subnet"
  dns_label         = "plasticsub"
  security_list_ids = [oci_core_security_list.plastic_detection_sl.id]
  route_table_id    = oci_core_route_table.plastic_detection_rt.id
  freeform_tags     = var.tags
}
