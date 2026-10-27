# 운송로봇의 별도 통합본 환경. 노드나 주행을 시작하지 않는다.
integration_robot_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
source /opt/ros/jazzy/setup.bash || return
source "$HOME/turtlebot3_ws/install/local_setup.bash" || return
source "$HOME/device_ws/install/local_setup.bash" || return
export TRANSPORT_INTEGRATION_BUILD_ROOT="$integration_robot_root/robot_build"
source "$integration_robot_root/scripts/env.bash" || return
