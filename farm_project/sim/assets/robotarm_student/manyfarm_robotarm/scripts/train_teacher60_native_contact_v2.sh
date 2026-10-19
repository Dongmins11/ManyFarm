#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
HARVEST_PY="${HARVEST_PY:-/home/bhc/isaac/env_isaaclab/bin/python}"
ready="${NATIVE_CONTACT_V2_READY:-$PWD/outputs/harvest_rl/native_contact_v2_ready_20261012.json}"
if [[ ! -x "$HARVEST_PY" || ! -f "$ready" ]]; then
  echo "Missing Python or new native-contact readiness pointer: $ready" >&2; exit 2
fi
# Reject stray pasted arguments before expensive asset hashing / simulator boot.
rest=("$@")
for ((i=0; i<${#rest[@]}; i++)); do
  case "${rest[i]}" in
    --execute) ;;
    --resume-checkpoint)
      ((i+=1))
      if [[ $i -ge ${#rest[@]} || ! -f "${rest[i]}" ]]; then
        echo '--resume-checkpoint requires an existing file from this new branch.' >&2; exit 2
      fi ;;
    *) echo "Unsupported argument: ${rest[i]}. Use ITERATIONS / NUM_ENVS; output is automatic." >&2; exit 2 ;;
  esac
done
mapfile -t evidence < <("$HARVEST_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["preflight"])' "$ready")
if [[ ${#evidence[@]} != 1 || ! -f "${evidence[0]}" ]]; then
  echo 'Invalid new preparation pointer.' >&2; exit 2
fi
prefix="${NATIVE_CONTACT_V2_OUT_PREFIX:-$PWD/runs/harvest_rl/teacher60_native_contact_v2_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$(dirname "$prefix")"
live_log="$(mktemp "${prefix}.XXXXXX.log")"
echo "OUTPUT: ${live_log%.log}"
echo "LIVE LOG: $live_log"
echo 'Warm start: latest native_alignment final; HOME/grasp is frozen; native pull/retention only.'
OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}" OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}" \
  "$HARVEST_PY" -u scripts/train_teacher60_native_contact_v2.py train \
  --num-envs "${NUM_ENVS:-2048}" --iterations "${ITERATIONS:-300}" \
  --preflight "${evidence[0]}" --output "${live_log%.log}" --headless "$@" 2>&1 | tee "$live_log"
if [[ -f "${live_log%.log}/teacher_final.pt" ]]; then
  "$HARVEST_PY" - "${live_log%.log}" <<'PY'
import hashlib,json,sys
from pathlib import Path
folder=Path(sys.argv[1]).resolve();run=json.loads((folder/'run.json').read_text())
if not run.get('completed') or not run.get('learning') or not run.get('source_still_matches'):
    raise SystemExit('Training did not complete; latest pointer is unchanged.')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checkpoint=folder/'teacher_final.pt'
pointer=Path('outputs/harvest_rl/native_contact_v2_last_train.json')
temporary=pointer.with_suffix('.tmp.json')
temporary.write_text(json.dumps(dict(checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),
    run_sha256=sha(folder/'run.json'),contract_sha256=run['contract_sha256']),indent=2)+'\n')
temporary.replace(pointer)
print('Completed checkpoint pointer:',pointer)
PY
fi
