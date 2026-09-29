#!/usr/bin/env bash
set -euo pipefail
farm_mode="${1:-sim}"
if [[ "$farm_mode" != sim && "$farm_mode" != real ]]; then
    echo 'mode는 sim 또는 real이어야 합니다.' >&2
    exit 2
fi
command -v colcon >/dev/null || { echo '현재 터미널에 colcon 환경이 필요합니다.' >&2; exit 2; }
farm_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
(cd "$farm_root/robot/ros_ws" && colcon build --symlink-install)
# ROS setup 스크립트는 미정의 환경변수를 읽을 수 있습니다.
set +u
source "$farm_root/robot/ros_ws/install/setup.bash"
if [[ "$farm_mode" == sim ]]; then
    (cd "$farm_root/sim/ros_ws" && colcon build --symlink-install)
fi
