#!/usr/bin/env bash
# 로봇 SSH 새 터미널. 기존 런치를 유지한 채 읽기 전용 측정만 수행한다.
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
out="$root/runs/wall_reference/$(date +%Y%m%d_%H%M%S)_$$"
python3 "$root/robot/tools/transfer/wall_reference_capture.py" \
  --scan-topic /harvest_01/scan_filtered --odom-topic /harvest_01/odom \
  --footprint-topic /harvest_01/local_costmap/published_footprint --output "$out" "$@"
printf '측정 기록: %s\n' "$out"
