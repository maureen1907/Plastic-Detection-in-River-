#!/bin/bash
# =============================================================================
# k3s master bootstrap
# =============================================================================
set -euxo pipefail

# Install k3s as a server (control plane).
# --write-kubeconfig-mode 644 makes /etc/rancher/k3s/k3s.yaml readable by ubuntu
# --tls-san adds the external IP to the cert so kubectl from outside works
# --disable traefik because we'll use a NodePort service (simpler, less to debug)
curl -sfL https://get.k3s.io | \
  K3S_TOKEN='${k3s_token}' \
  INSTALL_K3S_EXEC="server --write-kubeconfig-mode 644 --tls-san ${external_ip} --disable traefik" \
  sh -

# Wait for k3s to come up
until kubectl get nodes >/dev/null 2>&1; do
  sleep 2
done

echo "k3s master ready" > /var/log/k3s-bootstrap-done
