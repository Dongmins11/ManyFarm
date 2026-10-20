#!/usr/bin/env bash
# 기존 trial.bash/설정/드라이버를 변경하지 않는 선택형 시험 런치.
set -e
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
source /opt/ros/jazzy/setup.bash
source "$HOME/vicpinky_ws/install/setup.bash"
source "$root/robot/ros_ws/install/setup.bash"
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
cd "$root"
action="${1:-}"; shift || true
case "$action" in
  launch)
    mkdir -p "$HOME/.cache/manyfarm"
    exec 9>>"$HOME/.cache/manyfarm/harvest_trial.lock"
    flock -n 9 || { echo '기존 런치를 종료한 뒤 실행하세요.'; exit 3; }
    python3 robot/tools/tag_camera/bias_trial/launch_guard.py "$root"
    ros2 pkg prefix farm_arc_controller >/dev/null
    folder="$(python3 robot/tools/transfer/arc_trial.py prepare)"
    echo "시험 폴더: $folder"
    set -o pipefail
    ros2 launch farm_bringup harvest.launch.py project_root:="$root" mode:=real \
      environment_config:="$folder/environment.yaml" devices:=true navigation:=true \
      tag_correction:=true tag_camera:=true 2>&1 | tee "$folder/launch.log"
    ;;
  plan|execute)
    if [ "$action" = execute ]; then
      exec python3 robot/tools/transfer/arc_trial.py trial --execute "$@"
    else
      exec python3 robot/tools/transfer/arc_trial.py trial "$@"
    fi
    ;;
  *) echo '사용: arc_trial.bash {launch|plan|execute --exclusive --reference PLAN.json}'; exit 2;;
esac
