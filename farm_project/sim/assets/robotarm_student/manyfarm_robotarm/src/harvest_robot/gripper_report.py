"""Repeatable triangle-surface clearance measurement; no Isaac Sim needed."""
import json
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation
from harvest_rl.kinematics import ArmKinematics, origin
from harvest_rl.settings import URDF


def main():
    kin = ArmKinematics()
    centre = np.array([.0271, -.000218121, -.085])
    joint = kin.root.find("joint[@name='arm_2/gripper']")
    result = {"candidate_centre_in_gripper_m": centre.tolist(), "diameter_m": .070, "samples": []}
    for name, key in (("arm_2/gripper_link","wrist_roll_follower"),
                      ("arm_2/moving_jaw_so101_v1_link","moving_jaw")):
        for c in kin.root.find(f"link[@name='{name}']").findall("collision"):
            m = c.find("geometry/mesh")
            if m is None or key not in m.get("filename"):
                continue
            mesh = trimesh.load(URDF.parent / m.get("filename"))
            mesh.apply_transform(origin(c.find("origin")))
            for angle in ([0.] if "follower" in key else [.5,.8,1.1]):
                transformed = mesh.copy()
                if "moving" in key:
                    r = np.eye(4)
                    r[:3,:3] = Rotation.from_rotvec([0,0,angle]).as_matrix()
                    transformed.apply_transform(origin(joint.find("origin"))@r)
                closest, distance, _ = trimesh.proximity.closest_point_naive(transformed,centre[None])
                result["samples"].append({"mesh":key,"angle_rad":angle,
                    "surface_distance_m":float(distance[0]),"closest_point":closest[0].tolist()})
    result["caution"] = "Unsigned mesh clearance to a candidate sphere centre, not a validated grasp or pad calibration."
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
