# =============================================================================
# Outputs
# =============================================================================

output "master_external_ip" {
  description = "Public IP of the k3s master node"
  value       = google_compute_address.master_ip.address
}

output "master_internal_ip" {
  description = "Internal IP of the master (used by workers to join)"
  value       = google_compute_instance.master.network_interface[0].network_ip
}

output "worker_external_ips" {
  description = "Public IPs of the worker nodes"
  value       = [for w in google_compute_instance.worker : w.network_interface[0].access_config[0].nat_ip]
}

output "ssh_master" {
  description = "Convenience SSH command for the master node"
  value       = "ssh -i ~/.ssh/id_ed25519 ${var.ssh_user}@${google_compute_address.master_ip.address}"
}

output "kubectl_setup" {
  description = "One-liner to fetch the cluster kubeconfig locally"
  value       = "ssh -i ~/.ssh/id_ed25519 ${var.ssh_user}@${google_compute_address.master_ip.address} 'sudo cat /etc/rancher/k3s/k3s.yaml' | sed 's/127.0.0.1/${google_compute_address.master_ip.address}/' > ~/.kube/config-plastic"
}
