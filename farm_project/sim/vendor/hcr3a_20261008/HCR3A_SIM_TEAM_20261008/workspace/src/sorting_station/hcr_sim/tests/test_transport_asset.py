import unittest
import numpy as np
from hcr_sim.model import load_config
from hcr_sim.transport_asset import geometry, payload_positions, source_paths, URDF


class ExistingTransportTests(unittest.TestCase):
    def test_user_height_sets_payload_bottom_clearance(self):
        cfg = load_config()
        self.assertAlmostEqual(cfg['physics']['pepper_length'], .075)
        g = geometry()
        points = np.asarray(payload_positions(cfg, 4))
        # Changing height must preserve the bottom clearance, not the old center Z.
        expected_bottom = g['cargo_zero'][2] + g['floor_top'] + .006
        np.testing.assert_allclose(points[:, 2] - .075 / 2, expected_bottom)

    def test_original_resources_and_joint_limits(self):
        self.assertEqual(URDF.name, 'transport_robot.portable.urdf')
        for path in source_paths():
            self.assertTrue(path.is_file(), str(path))
        g = geometry()
        self.assertEqual(g['config']['box_width'], .3)
        np.testing.assert_allclose(g['cargo_zero'], [.086, 0, .255])
        self.assertAlmostEqual(g['limits']['box_tilt_joint'], np.pi/4)
        self.assertAlmostEqual(g['limits']['side_lid_joint'], np.pi/2)
        self.assertLessEqual(np.deg2rad(load_config()['transport']['tip_deg']),
                             g['limits']['box_tilt_joint'])

    def test_payload_starts_inside_existing_box_footprint(self):
        cfg = load_config()
        points = np.array(payload_positions(cfg, 4))
        local_x = cfg['transport']['start_front_x'] - points[:, 0]
        radius = cfg['physics']['pepper_diameter']/2
        self.assertTrue(np.all(local_x-radius >= -.3))
        self.assertTrue(np.all(local_x+radius <= 0))
        self.assertTrue(np.all(np.abs(points[:, 1])+radius < .15))
        self.assertTrue(np.all(points[:, 2] > .26))
        self.assertTrue(np.all(points[:, 2]+cfg['physics']['pepper_length']/2 < .445))

    def test_eight_peppers_fit_two_layers_inside_original_walls(self):
        cfg = load_config()
        g = geometry()
        points = np.asarray(payload_positions(cfg, 8))
        np.testing.assert_allclose(points[4:, :2], points[:4, :2])
        np.testing.assert_allclose(points[4:, 2] - points[:4, 2], .077)
        x = cfg['transport']['start_front_x'] - points[:, 0]
        radius = cfg['physics']['pepper_diameter'] / 2
        wall = g['config']['wall_thickness']
        self.assertTrue(np.all(x - radius > -g['config']['box_length'] + wall))
        self.assertTrue(np.all(x + radius < -wall))
        self.assertTrue(np.all(np.abs(points[:, 1]) + radius < g['config']['box_width']/2 - wall))
        self.assertTrue(np.all(points[:, 2] + .075 / 2 < g['cargo_zero'][2] + g['config']['box_height']))
        # Oversized fruit must be rejected rather than intersecting the source box.
        cfg['physics']['pepper_length'] = .105
        with self.assertRaisesRegex(ValueError, 'box height'):
            payload_positions(cfg, 8)
        cfg = load_config()
        cfg['physics']['pepper_diameter'] = .17
        with self.assertRaisesRegex(ValueError, 'footprint'):
            payload_positions(cfg, 8)
        with self.assertRaises(ValueError):
            payload_positions(load_config(), 9)


if __name__ == '__main__':
    unittest.main()
