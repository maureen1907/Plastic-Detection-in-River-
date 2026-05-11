# =============================================================================
# GCP infrastructure for the plastic-detection K8s cluster (k3s, 1 + 2)
#
# Provisions a VPC, firewall rules, and 3 GCE instances:
#   - 1 master (k3s server / control plane)
#   - 2 workers (k3s agent)
# Cloud-init installs k3s on each node and the workers auto-join the master.
# =============================================================================

# ---- Shared cluster join token --------------------------------------------
# k3s uses a single shared token for server <-> agent join.
# Generated once per cluster; persisted in Terraform state so reruns are stable.

resource "random_string" "k3s_token" {
  length  = 32
  special = false
  upper   = false
}

# ---- Networking: VPC + subnet ---------------------------------------------

resource "google_compute_network" "k8s_vpc" {
  name                    = "plastic-detection-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "k8s_subnet" {
  name          = "plastic-detection-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.k8s_vpc.id
}

# ---- Firewall rules --------------------------------------------------------

# SSH from anywhere
resource "google_compute_firewall" "allow_ssh" {
  name    = "plastic-detection-allow-ssh"
  network = google_compute_network.k8s_vpc.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["k8s-node"]
}

# k3s API + kubelet + NodePort range + app port
resource "google_compute_firewall" "allow_k8s_external" {
  name    = "plastic-detection-allow-k8s-external"
  network = google_compute_network.k8s_vpc.id

  allow {
    protocol = "tcp"
    ports = [
      "6443",          # k8s API server
      "8000",          # the plastic-detection API (direct, for testing)
      "30000-32767",   # NodePort service range
    ]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["k8s-node"]
}

# All-to-all inside the VPC: pod networking, etcd, kubelet, flannel VXLAN
resource "google_compute_firewall" "allow_internal" {
  name    = "plastic-detection-allow-internal"
  network = google_compute_network.k8s_vpc.id

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/24"]
  target_tags   = ["k8s-node"]
}

# ---- Master node -----------------------------------------------------------

resource "google_compute_address" "master_ip" {
  name = "plastic-detection-master-ip"
}

resource "google_compute_instance" "master" {
  name                      = "plastic-detection-master"
  machine_type              = var.machine_type
  zone                      = var.zone
  tags                      = ["k8s-node", "k8s-master"]
  labels                    = var.labels
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = var.boot_disk_image
      size  = var.boot_disk_size_gb
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.k8s_subnet.id
    access_config {
      nat_ip = google_compute_address.master_ip.address
    }
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(pathexpand(var.ssh_public_key_path))}"
  }

  # GCE startup-script: runs as root on first boot, equivalent of cloud-init user_data.
  metadata_startup_script = templatefile("${path.module}/cloud-init-master.sh.tpl", {
    k3s_token   = random_string.k3s_token.result
    external_ip = google_compute_address.master_ip.address
  })
}

# ---- Worker nodes ----------------------------------------------------------

resource "google_compute_instance" "worker" {
  count                     = var.worker_count
  name                      = "plastic-detection-worker-${count.index + 1}"
  machine_type              = var.machine_type
  zone                      = var.zone
  tags                      = ["k8s-node", "k8s-worker"]
  labels                    = var.labels
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = var.boot_disk_image
      size  = var.boot_disk_size_gb
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.k8s_subnet.id
    access_config {
      # ephemeral public IP - workers don't strictly need one but it makes SSH easier
    }
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${file(pathexpand(var.ssh_public_key_path))}"
  }

  metadata_startup_script = templatefile("${path.module}/cloud-init-worker.sh.tpl", {
    k3s_token = random_string.k3s_token.result
    master_ip = google_compute_instance.master.network_interface[0].network_ip
  })

  depends_on = [google_compute_instance.master]
}
