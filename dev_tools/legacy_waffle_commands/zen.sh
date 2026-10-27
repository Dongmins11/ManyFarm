#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
exec zenoh-bridge-ros2dds \
  -c "$HOME/.config/zenoh/waffle.json5" \
  --domain 77 \
  --ros-localhost-only \
  --no-multicast-scouting \
  -e tcp/192.168.0.20:7447 "$@"
