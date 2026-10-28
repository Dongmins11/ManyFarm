import unittest
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import linprog
from scipy.spatial import ConvexHull
from itertools import product
from hcr_sim.model import load_config
from hcr_sim.payload import pepper_bounds
from hcr_sim.transport_asset import geometry, payload_poses


class RandomPayloadTests(unittest.TestCase):
    def test_seed_reproduces_unordered_positions_and_orientations(self):
        cfg = load_config()
        poses = payload_poses(cfg, 8)
        self.assertEqual(poses, payload_poses(cfg, 8))
        cfg['transport']['payload_seed'] += 1
        self.assertNotEqual(poses, payload_poses(cfg, 8))
        points = np.asarray([p['position'] for p in poses])
        self.assertTrue(np.all(np.std(points, axis=0) > .02))
        quats = np.asarray([p['rotation_wxyz'] for p in poses])
        np.testing.assert_allclose(np.linalg.norm(quats, axis=1), 1.)
        self.assertGreater(np.std(quats[:, 0]), .1)

    def test_loading_envelopes_do_not_intersect_and_stay_over_opening(self):
        cfg, g = load_config(), geometry()
        center, half = pepper_bounds(cfg)
        offsets = np.asarray(list(product((-1, 1), repeat=3))) * half + center
        axis = np.array([cfg['transport']['start_front_x'], 0., g['cargo_zero'][2]])
        yaw = np.diag([-1., -1., 1.])
        for seed in (42, 43, 7):
            cfg['transport']['payload_seed'] = seed
            hulls = []
            for pose in payload_poses(cfg, 8):
                q = np.array(pose['rotation_wxyz'])
                rotation = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
                corners = (offsets @ rotation.T + pose['position'] - axis) @ yaw
                self.assertGreater(corners[:, 0].min(), -.295)
                self.assertLess(corners[:, 0].max(), -.005)
                self.assertLess(np.abs(corners[:, 1]).max(), .145)
                self.assertGreater(corners[:, 2].min(), g['config']['box_height'] + .03)
                hull = ConvexHull(corners).equations
                for other in hulls:
                    equations = np.vstack((hull, other))
                    # Independent LP intersection check of the two enclosures.
                    overlap = linprog(np.zeros(3), A_ub=equations[:, :3],
                        b_ub=-equations[:, 3], bounds=[(None, None)]*3, method='highs')
                    self.assertEqual(overlap.status, 2, 'initial bounding boxes intersect')
                hulls.append(hull)


if __name__ == '__main__':
    unittest.main()
