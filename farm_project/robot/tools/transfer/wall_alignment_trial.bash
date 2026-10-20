#!/usr/bin/env bash
# 로봇 SSH 전용. 실행 중인 기본 주행/Zenoh를 유지한다. 기본 check는 configure만 한다.
set -e
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
source "$root/robot/ros_ws/install/setup.bash"
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 pkg prefix farm_wall_controller >/dev/null
if [ "$#" -eq 0 ]; then set -- check; fi
python3 - "$root" "$@" <<'PY'
import sys,runpy
from pathlib import Path
import farm_navigation
root=Path(sys.argv[1]);args=sys.argv[2:]
sys.argv=['wall_alignment_trial',*args,'--namespace','/harvest_01',
          '--config',str(root/'robot/config/robots/vicpinky/transfer/wall_alignment_trial.json'),
          '--output',str(root/'runs/wall_alignment')]
runpy.run_module('farm_navigation.wall_trial_runtime',run_name='__main__')
PY
