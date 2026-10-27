#!/usr/bin/env bash
set -eo pipefail
integration_robot_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$integration_robot_root/scripts/robot_env.bash"
exec ros2 launch farm_bringup transport.launch.py \
  project_root:="$TRANSPORT_PROJECT_ROOT" \
  environment_config:=robot/config/environments/transport_docking_trial.yaml \
  mode:=real "$@"
