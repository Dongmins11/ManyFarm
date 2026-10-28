#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "$0")/env.bash"
exec ros2 launch farm_bringup scout.launch.py mode:=real project_root:="$scout_root/farm_project" environment_config:=robot/config/environments/scout_real.yaml headless:=true device:=cpu vision_python:="$HOME/pi_d435_setup/.venv/bin/python" tag_correction:=false tag_camera:=false "$@"
