#!/bin/bash
# =============================================================================
# k3s worker (agent) bootstrap
# =============================================================================
set -euxo pipefail

# Wait for the master's k3s API to be reachable before trying to join.
# The master cloud-init runs in parallel, so on a cold start we may need to wait.
until curl -k -sf --max-time 5 https://${master_ip}:6443/ping >/dev/null 2>&1 || \
      curl -k -sf --max-time 5 https://${master_ip}:6443/ >/dev/null 2>&1; do
  echo "waiting for k3s master at https://${master_ip}:6443"
  sleep 5
done

# Join as an agent (worker node)
curl -sfL https://get.k3s.io | \
  K3S_URL=https://${master_ip}:6443 \
  K3S_TOKEN='${k3s_token}' \
  sh -

echo "k3s agent ready" > /var/log/k3s-bootstrap-done
