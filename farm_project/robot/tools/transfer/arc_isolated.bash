#!/usr/bin/env bash
# 로봇 SSH에서 실행. 기존 주행 런치·초기 위치·Zenoh는 유지한다.
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
ros2 pkg prefix farm_arc_controller >/dev/null
exec python3 "$root/robot/tools/transfer/arc_isolated.py" "$@"
