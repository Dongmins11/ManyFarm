#!/usr/bin/env bash
set -eo pipefail
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export TRANSPORT_INTEGRATION_BUILD_ROOT=${TRANSPORT_INTEGRATION_BUILD_ROOT:-/tmp/transport_handoff_build_20261027}
if [[ "$TRANSPORT_INTEGRATION_BUILD_ROOT" == *[[:space:]]* ]]; then
  echo 'ROS interface build path must not contain whitespace.' >&2; exit 1
fi
mkdir -p "$TRANSPORT_INTEGRATION_BUILD_ROOT/src" "$integration_root/reports"
rsync -a --copy-unsafe-links --delete "$integration_root/farm_project/robot/ros_ws/src/" "$TRANSPORT_INTEGRATION_BUILD_ROOT/src/"
source /opt/ros/jazzy/setup.bash
cd "$TRANSPORT_INTEGRATION_BUILD_ROOT"
colcon build --symlink-install --executor sequential \
  --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release 2>&1 | tee "$integration_root/reports/build.log"
