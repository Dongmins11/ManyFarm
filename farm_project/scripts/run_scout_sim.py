#!/usr/bin/env python3
"""ROS 없이 시뮬레이션을 먼저 실행할 때. env_isaaclab Python을 사용하세요."""
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
for relative in ('robot/ros_ws/src/farm_common','sim/ros_ws/src/farm_sim_devices','sim/ros_ws/src/farm_sim_runtime'):
    sys.path.insert(0,str(root/relative))
if '--config' not in sys.argv:
    sys.argv+=['--config',str(root/'sim/ros_ws/src/farm_sim_config/config/scout.json')]
if '--assets-root' not in sys.argv:
    sys.argv+=['--assets-root',str(root/'sim/assets')]
from farm_sim_runtime.run_sim import main
if __name__=='__main__':main()
