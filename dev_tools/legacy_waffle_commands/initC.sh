#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
# Graph node20, heading node20 -> node3 (+Y, 90 degrees).
ros2 topic pub --once /transport_01/initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
'{header: {frame_id: map}, pose: {pose: {position: {x: 1.446, y: -1.120, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.7071067811865475, w: 0.7071067811865476}}, covariance: [0.04, 0, 0, 0, 0, 0, 0, 0.04, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0685]}}'
