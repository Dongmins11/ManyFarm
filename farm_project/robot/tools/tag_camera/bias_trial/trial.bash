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
# 2026-10-16 현장 관제 연결 기준: 로컬 DDS + 별도 Zenoh 브리지.
# source가 설정한 값도 정리한 후 적용한다. 브리지는 초기 위치 설정 후 별도 실행한다.
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER
unset ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
cd "$root"
case "$action" in
  rviz)
    exec rviz2 -d "$root/robot/config/robots/vicpinky/harvest_tag.rviz" --ros-args \
      -p use_sim_time:=false -r /tf:=/harvest_01/tf -r /tf_static:=/harvest_01/tf_static \
      -r /initialpose:=/harvest_01/initialpose
    ;;
  launch)
    # 새 시험 폴더/marker를 만들기 전에 중복 실행과 남은 장치 프로세스를 막는다.
    mkdir -p "$HOME/.cache/manyfarm"
    exec 9>>"$HOME/.cache/manyfarm/harvest_trial.lock"
    if ! flock -n 9; then
      printf '실행 중단: 이미 수확 launch가 실행 중입니다. 기존 실행 창을 확인하세요.\n' >&2
      exit 3
    fi
    python3 robot/tools/tag_camera/bias_trial/launch_guard.py "$root"
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
