#!/usr/bin/env bash
set -eo pipefail
fleet_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
source /opt/ros/jazzy/setup.bash
source "$HOME/turtlebot3_ws/install/local_setup.bash"
mkdir -p "$fleet_root/robot_build/src" "$fleet_root/reports"
rsync -a --copy-unsafe-links --delete "$fleet_root/farm_project/robot/ros_ws/src/" "$fleet_root/robot_build/src/"
cd "$fleet_root/robot_build"
export MAKEFLAGS=-j1 CMAKE_BUILD_PARALLEL_LEVEL=1
colcon build --symlink-install --executor sequential --packages-up-to farm_bringup farm_vision --allow-overriding nav2_controller --cmake-args -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release -Dnlohmann_json_DIR="$fleet_root/deps/nlohmann/share/cmake/nlohmann_json" 2>&1 | tee "$fleet_root/reports/robot_build.log"
