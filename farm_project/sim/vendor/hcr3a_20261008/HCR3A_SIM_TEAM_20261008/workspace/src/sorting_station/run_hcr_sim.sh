#!/usr/bin/env bash
set -euo pipefail
hcr_sim_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$hcr_sim_root"
hcr_sim_python="${ISAAC_PYTHON:-/home/bhc/isaac/env_isaaclab/bin/python}"
if [[ ! -x "$hcr_sim_python" ]]; then
  echo 'Set ISAAC_PYTHON to your Isaac Lab Python executable.' >&2
  exit 1
fi
exec "$hcr_sim_python" src/sorting_station/run_hcr_sim.py "$@"
