#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/waffle_commands/env.bash"
exec ros2 topic pub --once /transport_01/initialpose geometry_msgs/msg/PoseWithCovarianceStamped '{"header": {"frame_id": "map"}, "pose": {"pose": {"position": {"x": 1.44925261871214, "y": -1.4117056368030176, "z": 0.0}, "orientation": {"x": 0.0, "y": 0.0, "z": -0.6998559726728494, "w": 0.7142839894006724}}, "covariance": [0.04, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.04, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0685]}}'
