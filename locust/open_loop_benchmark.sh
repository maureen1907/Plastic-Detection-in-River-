#!/usr/bin/env bash
# =============================================================================
# Open-loop scaling benchmark using vegeta.
#
# Complements the closed-loop Locust benchmark by firing requests at a FIXED
# arrival rate (independent of response time), which reveals the saturation
# *point* (the arrival rate beyond which latency diverges) rather than the
# steady-state plateau a closed-loop test produces.
#
# For each pod count {1, 2, 4} and each target rate {1, 2, 3, 4, 5, 6} req/s,
# attack for 30 s and capture latency + error histograms.
#
# Output: open_loop_results/pods<N>_rate<R>.{txt,json}
# =============================================================================
set -euo pipefail

MASTER_IP="35.197.187.242"
NODEPORT=30080
ENDPOINT="http://${MASTER_IP}:${NODEPORT}/api/predict"
NAMESPACE=plastic-detection
DEPLOY=plastic-detection-api
DURATION=30s
SSH_KEY=~/.ssh/id_ed25519
SSH_OPTS="-o StrictHostKeyChecking=no -i ${SSH_KEY}"

POD_COUNTS=(1 2 4)
# Test rates from below-saturation through above. Saturation predicted at ~3 QPS
# per pod from closed-loop μ measurement, so go up to 2x expected ceiling.
RATES_PER_POD_COUNT_1=(1 2 3 4 5)
RATES_PER_POD_COUNT_2=(2 4 6 8 10)
RATES_PER_POD_COUNT_4=(4 6 8 10 12 14)

RESULTS_DIR="$(pwd)/open_loop_results"
mkdir -p "${RESULTS_DIR}"

TARGET_FILE=$(mktemp)
cat > "${TARGET_FILE}" <<EOF
POST ${ENDPOINT}
Content-Type: application/json
@$(pwd)/payload.json
EOF

scale_pods() {
  local n=$1
  echo "[scale] -> ${n} replicas"
  ssh ${SSH_OPTS} ubuntu@${MASTER_IP} \
    "sudo kubectl scale deployment/${DEPLOY} -n ${NAMESPACE} --replicas=${n}" \
    >/dev/null
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
  echo "[scale] TIMEOUT waiting for ${n} pods" >&2
  exit 1
}

run_attack() {
  local pods=$1 rate=$2
  local prefix="${RESULTS_DIR}/pods${pods}_rate${rate}"
  echo "[attack] pods=${pods} rate=${rate}/s duration=${DURATION}"
  vegeta attack -targets="${TARGET_FILE}" -rate="${rate}/s" -duration="${DURATION}" -timeout=30s \
    > "${prefix}.bin"
  vegeta report -type=text   "${prefix}.bin" > "${prefix}.txt"
  vegeta report -type=json   "${prefix}.bin" > "${prefix}.json"
  # Quick console summary
  awk 'NR==2 || /^Success/ || /^Latencies/ || /^Throughput/ || /^Status Codes/' "${prefix}.txt" || true
  sleep 3
}

START=$(date +%s)
for pods in "${POD_COUNTS[@]}"; do
  scale_pods "${pods}"
  sleep 15  # let probes settle + new pods warm up

  case "${pods}" in
    1) rates=("${RATES_PER_POD_COUNT_1[@]}");;
    2) rates=("${RATES_PER_POD_COUNT_2[@]}");;
    4) rates=("${RATES_PER_POD_COUNT_4[@]}");;
  esac

  for rate in "${rates[@]}"; do
    run_attack "${pods}" "${rate}"
  done
done
END=$(date +%s)

echo
echo "Open-loop benchmark complete in $(( (END-START)/60 )) min $(( (END-START)%60 )) s"
echo "Results in ${RESULTS_DIR}/"
ls -1 "${RESULTS_DIR}/" | head -20

rm -f "${TARGET_FILE}"
