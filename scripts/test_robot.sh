#!/usr/bin/env bash
set -eo pipefail
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$integration_root"
export PYTHONDONTWRITEBYTECODE=1
source scripts/robot_env.bash
python3 -B -m unittest discover -s tests -p test_integration.py
python3 -B -m unittest discover -s tests/protocol -p test_protocol_flow.py
export PYTHONPATH="$integration_root/farm_project/robot/ros_ws/src/harvest_robot:$integration_root/farm_project/robot/ros_ws/src/farm_navigation:$PYTHONPATH"
for suite in test_transfer_rotation.py test_transfer_restore.py test_staged_navigation.py; do
 python3 -B -m unittest discover -s farm_project/robot/ros_ws/src/harvest_robot/test -p "$suite"
done
echo 'PC-only: test_shared_navigation_policy.py (4 tests; simulation fixtures are not deployed).'
python3 -B -m unittest discover -s tests -p test_navigation_adapter.py
export PYTHONPATH="$integration_root/farm_project/robot/ros_ws/src/farm_docking:$integration_root/farm_project/robot/ros_ws/src/transport_robot:$PYTHONPATH"
python3 -B -m unittest discover -s tests -p test_review_regressions.py
