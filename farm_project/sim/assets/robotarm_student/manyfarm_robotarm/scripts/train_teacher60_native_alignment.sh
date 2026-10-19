#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
HARVEST_PY="${HARVEST_PY:-/home/bhc/isaac/env_isaaclab/bin/python}"
# This pointer is created only after matching no-update preflight and baseline.
ready="${NATIVE_ALIGNMENT_READY:-$PWD/outputs/harvest_rl/native_alignment_ready_20261012.json}"
if [[ ! -f "$ready" ]]; then
  echo "Missing preparation pointer: $ready" >&2; exit 2
fi
for arg in "$@"; do
  if [[ "$arg" == --output || "$arg" == --output=* || "$arg" == --preflight || "$arg" == --baseline-report ]]; then
    echo 'Use NATIVE_ALIGNMENT_OUT_PREFIX/READY; output folders are unique.' >&2; exit 2
  fi
done
mapfile -t evidence < <("$HARVEST_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["preflight"]); print(d["baseline_report"])' "$ready")
if [[ "${#evidence[@]}" != 2 || ! -f "${evidence[0]}" || ! -f "${evidence[1]}" ]]; then
  echo 'Invalid preparation pointer.' >&2; exit 2
fi
prefix="${NATIVE_ALIGNMENT_OUT_PREFIX:-$PWD/runs/harvest_rl/teacher60_native_alignment_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$(dirname "$prefix")"
live_log="$(mktemp "${prefix}.XXXXXX.log")"
echo "OUTPUT: ${live_log%.log}"
echo "LIVE LOG: $live_log"
OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}" OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}" \
  "$HARVEST_PY" -u scripts/train_teacher60_native_alignment.py train \
  --num-envs "${NUM_ENVS:-2048}" --iterations "${ITERATIONS:-500}" \
  --preflight "${evidence[0]}" --baseline-report "${evidence[1]}" \
  --output "${live_log%.log}" --headless "$@" 2>&1 | tee "$live_log"
