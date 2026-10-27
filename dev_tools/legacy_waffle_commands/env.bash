# 와플 ROS 작업공간 및 Zenoh 브리지용 로컬 DDS 환경.
source /opt/ros/jazzy/setup.bash || return
source "$HOME/turtlebot3_ws/install/setup.bash" || return
source "$HOME/transport_docking_20261013/ros_build/install/setup.bash" || return
source "$HOME/transport_protocol_20261018/install/local_setup.bash" || return
unset CYCLONEDDS_URI ROS_STATIC_PEERS ROS_DISCOVERY_SERVER
unset ROS_LOCALHOST_ONLY
unset FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST

# BEGIN STATION_RETURN_PACKAGE_PRIORITY
# Ensure protocol interfaces/server win over inherited old or trial overlays.
for waffle_prefix in "$HOME/transport_protocol_20261018/install/farm_interfaces" "$HOME/transport_protocol_20261018/install/transport_robot"; do
 export AMENT_PREFIX_PATH="$waffle_prefix${AMENT_PREFIX_PATH:+:$AMENT_PREFIX_PATH}"
 export PYTHONPATH="$waffle_prefix/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
 export LD_LIBRARY_PATH="$waffle_prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
done
unset waffle_prefix
# END STATION_RETURN_PACKAGE_PRIORITY

# Editable colcon Python package: .pth underlays must not win.
export PYTHONPATH="$HOME/transport_protocol_20261018/build/transport_robot${PYTHONPATH:+:$PYTHONPATH}"

# OpenCR mechanism bridge (UART owner launched once by bringup).
source "$HOME/device_ws/install/local_setup.bash" || return
