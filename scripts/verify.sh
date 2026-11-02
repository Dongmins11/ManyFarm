#!/usr/bin/env bash
set -eo pipefail
fleet_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$fleet_root"
source scripts/env.bash
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
mkdir -p reports
export PYTHONPATH="$fleet_root/farm_project/robot/ros_ws/src/farm_common/test:$PYTHONPATH"
export ROS_LOG_DIR=${ROS_LOG_DIR:-/tmp/fleet_main_integration_20261102_launch_logs}
bash scripts/test.sh
python3 -B -m unittest discover -s tests -p test_fleet_profiles.py
python3 -B -m pytest -q -p no:cacheprovider farm_project/robot/ros_ws/src/farm_common/test farm_project/robot/ros_ws/src/scout_robot/test/test_real_observation_recovery.py farm_project/robot/ros_ws/src/scout_robot/test/test_graph_harvest_goal.py farm_project/robot/ros_ws/src/scout_robot/test/test_far_depth_extension.py farm_project/robot/ros_ws/src/scout_robot/test/test_window_overlap.py
python3 -B -m pytest -q -p no:cacheprovider tests/test_main_merge.py farm_project/sim/tests/test_common_operation_clock.py farm_project/sim/tests/test_transport_sim_integration.py
ros2 launch farm_bringup scout.launch.py --show-args > reports/scout_launch_args.txt
ros2 launch farm_bringup transport.launch.py --show-args > reports/transport_launch_args.txt
