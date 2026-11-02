#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "$0")/runtime_env.bash" "${1:?scout or transport}"
shift
if [[ $fleet_role == transport ]]; then
  exec zenoh-bridge-ros2dds -c "$HOME/.config/zenoh/waffle.json5" --domain 77 --ros-localhost-only --no-multicast-scouting -e tcp/192.168.0.20:7447 "$@"
else
  exec zenoh-bridge-ros2dds --domain 77 --ros-localhost-only --no-multicast-scouting -e tcp/192.168.0.20:7447 "$@"
fi
