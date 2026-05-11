#!/usr/bin/env bash
# =============================================================================
# Scaling benchmark for FIT5225 A1.
#
# For each pod count in {1, 2, 4, 8}, runs Locust with progressively higher
# user counts in {1, 2, 4, 8, 16} for 45s each. Saves per-run CSVs to
# results/pods<N>_users<M>_*.csv.
#
# Run from this directory: ./benchmark.sh
# =============================================================================
set -euo pipefail

MASTER_IP="35.197.187.242"
WORKER_IPS=("34.151.134.152" "34.151.99.133")
NODEPORT=30080
NAMESPACE=plastic-detection
DEPLOY=plastic-detection-api
DURATION=45s
SSH_KEY=~/.ssh/id_ed25519
SSH_OPTS="-o StrictHostKeyChecking=no -i ${SSH_KEY}"

POD_COUNTS=(1 2 4 8)
USER_COUNTS=(1 2 4 8 16)

# Round-robin across master + all workers for fair load distribution
EXTRA_HOSTS_LIST=("http://${MASTER_IP}:${NODEPORT}")
for w in "${WORKER_IPS[@]}"; do
  EXTRA_HOSTS_LIST+=("http://${w}:${NODEPORT}")
done
EXTRA_HOSTS_CSV=$(IFS=, ; echo "${EXTRA_HOSTS_LIST[*]}")

RESULTS_DIR="$(pwd)/results"
mkdir -p "${RESULTS_DIR}"

echo "Benchmark plan:"
echo "  pods: ${POD_COUNTS[*]}"
echo "  users: ${USER_COUNTS[*]}"
echo "  duration: ${DURATION} per run"
echo "  hosts: ${EXTRA_HOSTS_CSV}"
echo "  output: ${RESULTS_DIR}/"
echo

scale_pods() {
  local n=$1
  echo "[scale] -> ${n} replicas"
  ssh ${SSH_OPTS} ubuntu@${MASTER_IP} \
    "sudo kubectl scale deployment/${DEPLOY} -n ${NAMESPACE} --replicas=${n}" \
    >/dev/null

  # Wait until all replicas are Ready (or 5 min timeout).
  local deadline=$(( $(date +%s) + 300 ))
  while (( $(date +%s) < deadline )); do
    local ready
    ready=$(ssh ${SSH_OPTS} ubuntu@${MASTER_IP} \
      "sudo kubectl get deployment ${DEPLOY} -n ${NAMESPACE} -o jsonpath='{.status.readyReplicas}'" \
      2>/dev/null)
    if [[ "${ready}" == "${n}" ]]; then
      echo "[scale] ${n}/${n} ready"
      return 0
    fi
    sleep 5
  done
  echo "[scale] TIMEOUT waiting for ${n} pods Ready" >&2
  exit 1
}

run_one() {
  local pods=$1 users=$2
  local prefix="${RESULTS_DIR}/pods${pods}_users${users}"
  echo "[run] pods=${pods} users=${users}"

  LOCUST_EXTRA_HOSTS="${EXTRA_HOSTS_CSV}" \
    python3 -m locust -f locustfile.py \
    --host "http://${MASTER_IP}:${NODEPORT}" \
    --users "${users}" \
    --spawn-rate "${users}" \
    --run-time "${DURATION}" \
    --headless \
    --csv "${prefix}" \
    --only-summary \
    2>&1 | tail -3 || true

  # Brief cool-down so the next run starts on a quiet cluster
  sleep 3
}

START_TS=$(date +%s)
for pods in "${POD_COUNTS[@]}"; do
  scale_pods "${pods}"
  # Brief settle time after scale (pods warming model into memory)
  sleep 10
  for users in "${USER_COUNTS[@]}"; do
    run_one "${pods}" "${users}"
  done
done
END_TS=$(date +%s)

echo
echo "Benchmark complete in $(( (END_TS - START_TS) / 60 )) min $(( (END_TS - START_TS) % 60 )) sec"
echo "Results in ${RESULTS_DIR}/"
ls -1 "${RESULTS_DIR}/" | head -20
