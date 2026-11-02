#!/usr/bin/env bash
# 로봇에서 명시적으로 실행한다. PC 준비 작업에서는 자동 호출하지 않는다.
set -eo pipefail
fleet_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
role=${1:-}; profile=${2:-current}
case "$role:$profile" in
  scout:current) env_file=robot/config/environments/scout_real.yaml ;;
  transport:current) env_file=robot/config/environments/transport_current.yaml ;;
  transport:candidate) env_file=robot/config/environments/transport_docking_trial.yaml ;;
  *) echo 'Usage: bringup.sh scout current | transport current | transport candidate' >&2; exit 2 ;;
esac
shift "$(( $# >= 2 ? 2 : $# ))"
source "$fleet_root/scripts/runtime_env.bash" "$role"
if [[ $role == scout ]]; then
  exec ros2 launch farm_bringup scout.launch.py mode:=real project_root:="$fleet_root/farm_project" environment_config:="$env_file" headless:=true device:=cpu vision_python:="$HOME/pi_d435_setup/.venv/bin/python" tag_correction:=false tag_camera:=false "$@"
else
  exec ros2 launch farm_bringup transport.launch.py mode:=real project_root:="$fleet_root/farm_project" environment_config:="$env_file" devices:=true navigation:=true allow_route_checks:=true "$@"
fi
