#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
HARVEST_PY="${HARVEST_PY:-/home/bhc/isaac/env_isaaclab/bin/python}"
ready="${CONTACT_CONSERVATIVE_READY:-$PWD/outputs/harvest_rl/native_contact_conservative_ready.json}"
if [[ ! -x "$HARVEST_PY" || ! -f "$ready" ]]; then
  echo "Missing interpreter or conservative preparation pointer: $ready" >&2; exit 2
fi
execute=false
resume=()
while (($#)); do
  case "$1" in
    --execute) execute=true; shift ;;
    --resume-checkpoint)
      [[ $# -ge 2 && -f "$2" ]] || { echo 'Existing resume checkpoint required.' >&2; exit 2; }
      resume=(--resume-checkpoint "$2"); shift 2 ;;
    *) echo "Unsupported argument: $1" >&2; exit 2 ;;
  esac
done
mapfile -t paths < <("$HARVEST_PY" - "$ready" <<'PY'
import hashlib,json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
for key in ('preflight','warm_checkpoint'):
    p=Path(d[key]); h=hashlib.sha256(p.read_bytes()).hexdigest()
    if h!=d[key+'_sha256']: raise SystemExit('Changed readiness evidence: '+key)
    print(p)
PY
)
[[ ${#paths[@]} == 2 ]] || { echo 'Readiness evidence verification failed.' >&2; exit 2; }
echo "TRANSFER CHECKPOINT: ${paths[1]}"
echo "ITERATIONS: ${ITERATIONS:-600}; ENVS: ${NUM_ENVS:-2048}; physics60Hz / policy20Hz"
echo 'Native arm5 pull/retention only; HOME grasp and physical gates stay fixed.'
$execute || { echo 'Plan only. Add --execute to start in background.'; exit 0; }
prefix="$PWD/runs/harvest_rl/teacher60_native_contact_conservative_$(date +%Y%m%d_%H%M%S)"
live_log="$(mktemp "${prefix}.XXXXXX.log")"
output="${live_log%.log}"
nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  "$HARVEST_PY" -u scripts/train_teacher60_native_contact_conservative.py train \
  --warm-checkpoint "${paths[1]}" --preflight "${paths[0]}" \
  --num-envs "${NUM_ENVS:-2048}" --iterations "${ITERATIONS:-600}" \
  --output "$output" --headless --execute "${resume[@]}" \
  >"$live_log" 2>&1 </dev/null &
task_pid=$!
"$HARVEST_PY" - "$output" "$live_log" "$task_pid" "${paths[1]}" <<'PY'
import json,sys
from pathlib import Path
out,log,pid,warm=sys.argv[1:]
p=Path('outputs/harvest_rl/native_contact_conservative_last_launch.json')
t=p.with_suffix('.tmp.json')
t.write_text(json.dumps(dict(output=out,log=log,pid=int(pid),warm_checkpoint=warm,
    status='launched_not_yet_verified',hardware_executed=False),indent=2)+'\n');t.replace(p)
PY
echo "PID: $task_pid"
echo "OUTPUT: $output"
echo "LOG: $live_log"
printf 'View: tail -f %q\n' "$live_log"
echo 'Background training survives terminal closure; restarting the PC interrupts it.'
