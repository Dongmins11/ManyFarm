#!/usr/bin/env bash
set -eo pipefail
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export TRANSPORT_INTEGRATION_BUILD_ROOT=${TRANSPORT_INTEGRATION_BUILD_ROOT:-/tmp/fleet_main_integration_20261102_build}
if [[ "$TRANSPORT_INTEGRATION_BUILD_ROOT" == *[[:space:]]* ]]; then
  echo 'ROS interface build path must not contain whitespace.' >&2; exit 1
fi
mkdir -p "$TRANSPORT_INTEGRATION_BUILD_ROOT/src" "$integration_root/reports"
rsync -a --copy-unsafe-links --delete "$integration_root/farm_project/robot/ros_ws/src/" "$TRANSPORT_INTEGRATION_BUILD_ROOT/src/"
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
source /opt/ros/jazzy/setup.bash
cd "$TRANSPORT_INTEGRATION_BUILD_ROOT"
colcon build --symlink-install --executor sequential \
  --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release -Dnlohmann_json_DIR="$integration_root/deps/nlohmann/share/cmake/nlohmann_json" 2>&1 | tee "$integration_root/reports/build.log"
