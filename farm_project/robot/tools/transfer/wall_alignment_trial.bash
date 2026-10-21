#!/usr/bin/env bash
# 로봇 SSH 전용. 실행 중인 기본 주행/Zenoh를 유지한다. 기본 check는 configure만 한다.
set -e
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [ "${HARVEST_PC_CHECK:-0}" = 1 ]; then
  # 명시 PC 격리 검사에서만 사전 로딩한 독립 설치본을 사용한다.
  test "${ROS_DOMAIN_ID:-}" = 95
  test "${ROS_LOCALHOST_ONLY:-}" = 1
  test "${RMW_IMPLEMENTATION:-}" = rmw_fastrtps_cpp
  python3 "$root/robot/tools/transfer/pc_check_environment.py" "$root"
else
  source /opt/ros/jazzy/setup.bash
  source /home/vic/vicpinky_ws/install/setup.bash
  source "$root/robot/ros_ws/install/setup.bash"
  unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
  unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  export ROS_DOMAIN_ID=77
  export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
fi
ros2 pkg prefix farm_wall_controller >/dev/null
if [ "$#" -eq 0 ]; then set -- check; fi
python3 - "$root" "$@" <<'PY'
import sys,runpy
from pathlib import Path
import farm_navigation
root=Path(sys.argv[1]);args=sys.argv[2:]
sys.argv=['wall_alignment_trial','--namespace','/harvest_01',
          '--config',str(root/'robot/config/robots/vicpinky/transfer/wall_alignment_trial.json'),
          '--output',str(Path.home()/'Downloads/wall_alignment'),*args]
runpy.run_module('farm_navigation.wall_trial_runtime',run_name='__main__')
PY
