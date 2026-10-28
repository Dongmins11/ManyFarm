"""OMX sorting-station simulation and Mimic data-generation support.

This package is intentionally separate from src/harvest_robot/harvest_rl.
Shared robot/station geometry is read from smartfarm_description only.
"""

# Keep package import lightweight. In particular, the physical OMX-L sender
# must run inside the user's LeRobot environment without pulling in SciPy/Isaac.
# Import concrete modules explicitly where they are needed.

__all__: list[str] = []
