#!/usr/bin/env bash
scout_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
source /opt/ros/jazzy/setup.bash || return
source "$HOME/turtlebot3_ws/install/local_setup.bash" || return
source "$scout_root/robot_build/install/local_setup.bash" || return
export ROS_DOMAIN_ID=77 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export TURTLEBOT3_MODEL=burger LDS_MODEL=LDS-02
