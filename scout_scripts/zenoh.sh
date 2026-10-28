#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "$0")/env.bash"
exec zenoh-bridge-ros2dds --domain 77 --ros-localhost-only --no-multicast-scouting -e tcp/192.168.0.20:7447 "$@"
