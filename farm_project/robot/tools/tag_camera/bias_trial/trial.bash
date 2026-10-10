#!/usr/bin/env bash
# 입력: launch [on|off], goal, collect, rviz. goal만 실제 이동을 요청한다.
set -e
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)"
action="${1:-}"
source /opt/ros/jazzy/setup.bash
if [ "$action" != rviz ]; then
  source "$HOME/vicpinky_ws/install/setup.bash"
  source "$root/robot/ros_ws/install/setup.bash"
fi
export ROS_DOMAIN_ID=156
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ROS_LOCALHOST_ONLY ROS_DISCOVERY_SERVER ROS_STATIC_PEERS
cd "$root"
case "$action" in
  rviz)
    exec rviz2 -d "$root/robot/config/robots/vicpinky/harvest_tag.rviz" --ros-args \
      -p use_sim_time:=false -r /tf:=/harvest_01/tf -r /tf_static:=/harvest_01/tf_static \
      -r /initialpose:=/harvest_01/initialpose
    ;;
  launch)
    mode="${2:-on}"
    folder="$(python3 robot/tools/tag_camera/bias_trial/trial.py prepare --mode "$mode")"
    printf '시험 폴더: %s\n보상: %s\n' "$folder" "$mode"
    set -o pipefail
    ros2 launch farm_bringup harvest.launch.py project_root:="$root" mode:=real \
      environment_config:="$folder/environment.yaml" devices:=true navigation:=true \
      tag_correction:=true tag_camera:=true 2>&1 | tee "$folder/launch.log"
    ;;
  goal|collect|ready)
    exec python3 robot/tools/tag_camera/bias_trial/trial.py "$action"
    ;;
  *) printf '사용: bash %s {launch [on|off]|rviz|goal|ready|collect}\n' "$0"; exit 2 ;;
esac
