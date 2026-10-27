#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
export TURTLEBOT3_MODEL=waffle LDS_MODEL=LDS-03
exec ros2 launch farm_bringup transport.launch.py \
  project_root:="$HOME/transport_docking_20261013" \
  mode:=real \
  environment_config:=robot/config/environments/transport_docking_trial.yaml \
  devices:=true navigation:=true allow_route_checks:=true "$@"
