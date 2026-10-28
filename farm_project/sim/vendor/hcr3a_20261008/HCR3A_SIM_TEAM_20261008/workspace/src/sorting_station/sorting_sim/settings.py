"""Paths and constants for the OMX sorting simulation.

No imports from harvest_robot are allowed here. The only shared inputs are
assets under smartfarm_description and bell-pepper visual assets.
"""

from pathlib import Path

SORTING_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SORTING_ROOT.parents[1]
DESCRIPTION_ROOT = WORKSPACE_ROOT / "src" / "smartfarm_description"

SORTING_URDF = DESCRIPTION_ROOT / "urdf" / "sorting_station.urdf"
LEADER_URDF = DESCRIPTION_ROOT / "urdf" / "upstream" / "omx_l.urdf"
PEPPER_ASSET_ROOT = WORKSPACE_ROOT / "src" / "Pepper_RL_Demo" / "assets"
OUTPUT_ROOT = WORKSPACE_ROOT / "outputs" / "sorting_station"
ASSET_CACHE = OUTPUT_ROOT / "assets"
CAMERA_CONFIG = SORTING_ROOT / "config" / "d435_overhead.json"
WRIST_CAMERA_CONFIG = SORTING_ROOT / "config" / "u20cam_720p_wrist.json"
PEPPER_PHYSICS_CONFIG = SORTING_ROOT / "config" / "pepper_physics.json"
SIM_VISUAL_CONFIG = SORTING_ROOT / "config" / "sim_visuals.json"
SORTING_GEOMETRY_CONFIG = DESCRIPTION_ROOT / "config" / "sorting.json"

# ROBOTIS OMX-F follower: 5 arm joints + 1 actuated gripper.
ARM_JOINT_NAMES = ("omx_joint1", "omx_joint2", "omx_joint3", "omx_joint4", "omx_joint5")
GRIPPER_JOINT_NAME = "omx_gripper_joint_1"
EEF_BODY_NAME = "omx_link5"
TCP_LINK_NAME = "omx_end_effector_link"
TCP_OFFSET_XYZ_M = (0.09193, -0.0016, 0.0)

# Conservative task-space bounds in the sorting_station articulation root frame.
# These are safety clamps for teleoperation, not reachability guarantees.
TCP_WORKSPACE_MIN = (-0.30, -0.28, 0.08)
TCP_WORKSPACE_MAX = (0.26, 0.28, 0.48)

# Keep a small empty-jaw clearance. Commanding exactly 0 rad makes the two
# collision meshes fight the position drive when self-collision is enabled.
DEFAULT_SIM_GRIPPER_CLOSED = 0.10
# MoveIt names 1.0 rad as "open", but the physical OMX-F gripper can open
# substantially farther. Use the photographed/mechanical teleop range here.
DEFAULT_SIM_GRIPPER_NEUTRAL = 1.10
DEFAULT_SIM_GRIPPER_OPEN = 1.40

# Limit jaw target slew so opening the high-friction gripper does not catapult
# a released pepper. Closing may be faster than opening.
GRIPPER_OPEN_RATE_RAD_S = 1.1
GRIPPER_CLOSE_RATE_RAD_S = 4.0
