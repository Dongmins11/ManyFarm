#!/usr/bin/env bash
set -eo pipefail
fleet_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
source "$fleet_dir/scripts/runtime_env.bash" "${1:?scout or transport}"
exec python3 "$fleet_dir/scripts/initial_pose.py" "$@"
