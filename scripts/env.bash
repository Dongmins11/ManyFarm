# Source in a fresh shell. Does not start nodes or publish any command.
integration_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export TRANSPORT_PROJECT_ROOT="$integration_root/farm_project"
export TRANSPORT_INTEGRATION_BUILD_ROOT=${TRANSPORT_INTEGRATION_BUILD_ROOT:-/tmp/transport_handoff_build_20261027}
source /opt/ros/jazzy/setup.bash || return
# Optional separately-built hardware underlay, never auto-source the old robot workspace.
if [[ -n "${TRANSPORT_HARDWARE_SETUP:-}" ]]; then source "$TRANSPORT_HARDWARE_SETUP" || return; fi
if [[ ! -f "$TRANSPORT_INTEGRATION_BUILD_ROOT/install/local_setup.bash" ]]; then
  echo "Run bash '$integration_root/scripts/build.sh' first." >&2; return 1
fi
source "$TRANSPORT_INTEGRATION_BUILD_ROOT/install/local_setup.bash" || return
export ROS_DOMAIN_ID=77
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
