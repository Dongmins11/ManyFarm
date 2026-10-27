#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
# Graph node17, heading node17 -> node15 (-X, 180 degrees).
ros2 topic pub --once /transport_01/initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
'{header: {frame_id: map}, pose: {pose: {position: {x: 2.981, y: -1.333, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 1.0, w: 0.0}}, covariance: [0.04, 0, 0, 0, 0, 0, 0, 0.04, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0685]}}'
