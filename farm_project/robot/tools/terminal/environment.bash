#!/usr/bin/env bash
# Jazzy → 드라이버 → 프로젝트 순서. 이전 overlay의 setup 체인을 따라가지 않는다.
# 이전 셸에 source된 overlay가 프로젝트 설치본을 가리지 않도록 다시 구성한다.
unset AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
source /home/vic/vmany/main/farm_project/robot/ros_ws/install/local_setup.bash
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
