#!/usr/bin/env bash
set -eo pipefail
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$integration_root"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -p test_integration.py
python3 -B -m unittest discover -s tests/protocol -p test_protocol_flow.py
harvest_tests=farm_project/robot/ros_ws/src/harvest_robot/test
export PYTHONPATH="$integration_root/farm_project/robot/ros_ws/src/harvest_robot:$integration_root/farm_project/robot/ros_ws/src/farm_navigation${PYTHONPATH:+:$PYTHONPATH}"
for suite in test_transfer_rotation.py test_transfer_restore.py test_shared_navigation_policy.py test_staged_navigation.py; do
  python3 -B -m unittest discover -s "$harvest_tests" -p "$suite"
done
source "$integration_root/scripts/env.bash"
python3 -B -m unittest discover -s tests -p test_navigation_adapter.py
# 실제 소스를 검사한다. 빌드 복사본에만 수정이 남는 일을 피한다.
export PYTHONPATH="$integration_root/farm_project/robot/ros_ws/src/farm_docking:$integration_root/farm_project/robot/ros_ws/src/transport_robot:$PYTHONPATH"
python3 -B -m unittest discover -s tests -p test_review_regressions.py
