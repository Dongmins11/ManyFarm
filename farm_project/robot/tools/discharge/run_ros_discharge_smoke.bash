#!/usr/bin/env bash
# PC eunbi 새 터미널용. 별도 임시 빌드로 기존 install을 변경하지 않는다.
set -eo pipefail
project=/home/eunbi/vmany/main/farm_project
source /opt/ros/jazzy/setup.bash
trial_dir="$(mktemp -d /home/eunbi/harvest_stage5_ros_XXXXXX)"
echo "PC 시험 빌드/로그: $trial_dir"
cd "$project/robot/ros_ws"
colcon --log-base "$trial_dir/log" build \
  --base-paths src/farm_interfaces \
  --build-base "$trial_dir/build" \
  --install-base "$trial_dir/install"
source "$trial_dir/install/setup.bash"
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER
unset ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
python3 "$project/robot/tools/discharge/ros_discharge_smoke.py" 2>&1 | tee "$trial_dir/ros_smoke.log"
