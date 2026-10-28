import copy
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from hcr_sim.model import load_config, Arm, teach, lane_centers, ramp_surface_z, ROOT


class ModelTests(unittest.TestCase):
    def test_four_lanes_fit_note_width(self):
        cfg = load_config()
        lanes = lane_centers(cfg)
        self.assertEqual(list(lanes), list("ABCD"))
        self.assertEqual(list(lanes.values()), [0.1875, 0.0625, -0.0625, -0.1875])
        r = cfg["intake"]
        run = (r["slope_length"] ** 2 - r["rise"] ** 2) ** 0.5
        self.assertAlmostEqual(
            ramp_surface_z(cfg, r["low_x"] + run) - cfg["base_z"], 0.225
        )

    def test_all_teaching_poses_reachable(self):
        cfg = load_config()
        arm = Arm(cfg)
        poses = teach(cfg)
        self.assertEqual(len(poses), 14)
        for name, pose in poses.items():
            self.assertLess(
                np.linalg.norm(arm.fk(pose["q"])[:3, 3] - pose["xyz"]), 0.002, name
            )
            self.assertTrue(np.all(np.array(pose["q"]) >= arm.lower))
            self.assertTrue(np.all(np.array(pose["q"]) <= arm.upper))
        self.assertGreater(poses["RED"]["xyz"][1], 0)
        self.assertLess(poses["YELLOW"]["xyz"][1], 0)

    def test_urdf_joint_axes_match_kinematics(self):
        cfg = load_config()
        arm = Arm(cfg)
        root = ET.parse(
            ROOT / "src/smartfarm_description/urdf/hcr3a_functional.urdf"
        ).getroot()
        for i in range(6):
            j = root.find(f"joint[@name='joint{i+1}']")
            np.testing.assert_allclose(
                np.fromstring(j.find("origin").get("xyz"), sep=" "), arm.origins[i]
            )
            np.testing.assert_allclose(
                np.fromstring(j.find("axis").get("xyz"), sep=" "), arm.axes[i]
            )
        self.assertEqual(
            len([j for j in root.findall("joint") if j.get("type") == "revolute"]), 6
        )
        self.assertEqual(
            len([j for j in root.findall("joint") if j.get("type") == "prismatic"]), 2
        )
        self.assertIsNone(root.find("link[@name='tcp']/collision"))

    def test_no_harvest_runtime_dependency(self):
        for path in (ROOT / "src/sorting_station/hcr_sim").glob("*.py"):
            self.assertNotIn("import harvest_", path.read_text())


if __name__ == "__main__":
    unittest.main()
