#!/usr/bin/env bash
# =============================================================================
# build_submission.sh - Package the FIT5225 A1 deliverable .zip
#
# Includes everything the rubric asks for (Dockerfile, source code, K8s
# manifests, Locust client, experiment automation, IaC scripts, README).
# Excludes secrets, state, caches, training artefacts, and the .venv.
#
# Output: ./submission/mpha0039_plastic-detection.zip
# =============================================================================
set -euo pipefail

STUDENT_ID="mpha0039"
ZIP_NAME="${STUDENT_ID}_plastic-detection.zip"
WORK_DIR="$(pwd)"
STAGING_DIR="$(pwd)/submission/staging"
OUTPUT_DIR="$(pwd)/submission"

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}" "${OUTPUT_DIR}"

echo "Staging files into ${STAGING_DIR}..."

# ---- 1. Dockerfile + Docker compose ----
cp Dockerfile "${STAGING_DIR}/"
cp docker-compose.yml "${STAGING_DIR}/" 2>/dev/null || true

# ---- 2. Web service source code ----
cp main.py model.py service.py utils.py app.py "${STAGING_DIR}/"
cp requirements*.txt "${STAGING_DIR}/"
cp test_api.py "${STAGING_DIR}/" 2>/dev/null || true

# ---- 3. K8s manifests ----
mkdir -p "${STAGING_DIR}/k8s"
cp k8s/namespace.yaml k8s/deployment.yaml k8s/service.yaml k8s/README.md \
   "${STAGING_DIR}/k8s/"

# ---- 4. Locust client script + 5. Experiment automation ----
mkdir -p "${STAGING_DIR}/locust"
cp locust/locustfile.py locust/benchmark.sh locust/analyze.py \
   locust/README.md locust/REPORT_DRAFT.md \
   "${STAGING_DIR}/locust/"
# Include the plots and aggregated CSVs (compact + valuable evidence)
mkdir -p "${STAGING_DIR}/locust/plots"
cp locust/plots/*.png locust/plots/*.csv "${STAGING_DIR}/locust/plots/" 2>/dev/null || true
# Include the raw per-run CSVs for reproducibility (80 files, ~200 KB total)
mkdir -p "${STAGING_DIR}/locust/results"
cp locust/results/*.csv "${STAGING_DIR}/locust/results/" 2>/dev/null || true

# ---- 6. IaC scripts ----
# Copy GCP + OCI Terraform, preserving the directory layout.
# (Using a while-loop because `cp --parents` is GNU-only and not in BSD/macOS.)
for tf_root in gcp-terraform oci-terraform; do
  find "${tf_root}" -type f \
    \( -name '*.tf' -o -name '*.tpl' -o -name '*.sh.tpl' -o -name '*.example' \) \
    -not -path '*/.terraform/*' -print0 | while IFS= read -r -d '' f; do
      mkdir -p "${STAGING_DIR}/$(dirname "$f")"
      cp "$f" "${STAGING_DIR}/$f"
    done
done

# ---- 7. README + interview-prep docs ----
cp README.md "${STAGING_DIR}/"
mkdir -p "${STAGING_DIR}/docs"
cp docs/*.md "${STAGING_DIR}/docs/" 2>/dev/null || true

# ---- Safety check: no secrets, state, or huge artefacts ----
echo
echo "Safety check - the staged folder should NOT contain any of these:"
banned_patterns=(
  "*.tfvars"          # secrets (we keep only .tfvars.example)
  "*.tfstate*"        # state
  "*.pem"             # private keys
  ".terraform"        # provider cache
  "yolov8m.pt"        # 50 MB model checkpoint
  "best.pt"           # fine-tuned weights
  "__pycache__"
  ".venv"
  "venv"
  ".DS_Store"
)
FOUND_BAD=0
for pattern in "${banned_patterns[@]}"; do
  matches=$(find "${STAGING_DIR}" -name "${pattern}" 2>/dev/null)
  if [[ -n "${matches}" ]]; then
    echo "  ⚠  Found banned: ${matches}"
    FOUND_BAD=1
  fi
done
if [[ ${FOUND_BAD} -eq 0 ]]; then
  echo "  ✓ Clean (no secrets, state, weights, caches)"
fi

# ---- Verify .tfvars.example DID make it in (we DO want these) ----
echo
echo "Expected .tfvars.example files (template, NOT secret):"
find "${STAGING_DIR}" -name "*.tfvars.example" | sed 's|^|  |'

# ---- Show staging contents ----
echo
echo "Staging layout:"
(cd "${STAGING_DIR}" && find . -type f | sort | sed 's|^|  |')

# ---- Create the zip ----
ZIP_PATH="${OUTPUT_DIR}/${ZIP_NAME}"
rm -f "${ZIP_PATH}"
(cd "${STAGING_DIR}" && zip -rq "${ZIP_PATH}" . -x "*.DS_Store")

# ---- Final stats ----
echo
echo "Built: ${ZIP_PATH}"
echo "Size:  $(du -h "${ZIP_PATH}" | cut -f1)"
echo "Files: $(unzip -l "${ZIP_PATH}" | tail -1 | awk '{print $2}')"
