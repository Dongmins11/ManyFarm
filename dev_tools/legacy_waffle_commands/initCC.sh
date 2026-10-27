#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
# node10 -> node11, map frame; generated from operating graph.geojson.
ros2 topic pub --once /transport_01/initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
'{"header": {"frame_id": "map"}, "pose": {"pose": {"position": {"x": 0.046, "y": -0.035, "z": 0.0}, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}, "covariance": [0.04, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0685]}}'
