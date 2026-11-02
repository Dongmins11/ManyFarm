# 로봇 실행 환경. 기존 업무 overlay는 source하지 않는다.
fleet_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fleet_role=${1:-}
case "$fleet_role" in scout|transport) ;; *) echo 'role must be scout or transport' >&2; return 2;; esac
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
source /opt/ros/jazzy/setup.bash || return
source "$HOME/turtlebot3_ws/install/local_setup.bash" || return
export TRANSPORT_INTEGRATION_BUILD_ROOT=${FLEET_BUILD_ROOT:-$fleet_root/robot_build}
source "$fleet_root/scripts/env.bash" || return
export TURTLEBOT3_MODEL=$([[ $fleet_role == scout ]] && echo burger || echo waffle)
export LDS_MODEL=$([[ $fleet_role == scout ]] && echo LDS-02 || echo LDS-03)
