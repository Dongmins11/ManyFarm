"""시각 수확 시험의 정차 후보와 보수적인 지도 footprint 경계를 검사한다."""
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for package in ('farm_sim_runtime', 'farm_sim_devices'):
    sys.path.insert(0, str(ROOT/'sim/ros_ws/src'/package))
from farm_sim_devices.teacher_device import continuous_near_mask
from farm_sim_runtime.harvest_test_placement import find_placements, footprint_is_clear


def pose(x: float, y: float, z: float = 0., yaw: float = 0.) -> np.ndarray:
    """독립적인 시험용 강체 변환이다."""
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0., x], [s, c, 0., y], [0., 0., 1., z], [0., 0., 0., 1.]])


class PlacementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.device = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/teacher_policy.json').read_text())['device']
        self.mount = pose(.19, .185, .713, math.pi/2.)
        self.sections = {
            'WEST': dict(evaluation_bed_prim='/Bed', harvest_route=dict(x_m=2.5, heading_rad=-math.pi/2.),
                survey_geometry=dict(start_xy_m=[2., 5.], end_xy_m=[2., -3.])),
            'EAST': dict(evaluation_bed_prim='/Bed', harvest_route=dict(x_m=3.5, heading_rad=math.pi/2.),
                survey_geometry=dict(start_xy_m=[4., -3.], end_xy_m=[4., 5.]))}
        self.records = [dict(prim_path='/Bed/red', color='red'), dict(prim_path='/Bed/yellow', color='yellow')]
        self.points = np.array([(pose(x, y, yaw=yaw) @ self.mount @ np.array([.32, 0., .27, 1.]))[:3]
            for x, y, yaw in ((2.5, 1.2, -math.pi/2.), (3.5, 2.2, math.pi/2.))])

    def placements(self, **changes: object) -> list[dict]:
        arguments = dict(records=self.records, positions=self.points, attached=np.ones(len(self.records), dtype=bool),
            excluded_ids=set(), sections=self.sections, T_map_world=np.eye(4), T_base_arm=self.mount,
            base_z_map=0., device_config=self.device)
        arguments.update(changes)
        return find_placements(**arguments)

    def assert_candidate_geometry(self, placements: list[dict], points: np.ndarray) -> None:
        paths = [item['prim_path'] for item in self.records]
        for candidate in placements:
            self.assertGreaterEqual(candidate['y'], -3.)
            self.assertLessEqual(candidate['y'], 5.)
            route = self.sections[candidate['section_id']]['harvest_route']
            self.assertEqual(candidate['x'], route['x_m'])
            self.assertEqual(candidate['yaw'], route['heading_rad'])
            inverse = np.linalg.inv(np.asarray(candidate['T_world_base']) @ self.mount)
            for target in candidate['target_ids']:
                arm = (inverse @ np.r_[points[paths.index(target)], 1.])[:3]
                self.assertTrue(continuous_near_mask(arm[None, :], self.device)[0])

    def test_both_bed_sides_stay_on_original_routes_and_inside_teacher_range(self) -> None:
        candidates = self.placements()
        self.assertEqual({item['section_id'] for item in candidates}, {'WEST', 'EAST'})
        self.assertEqual({target for item in candidates for target in item['target_ids']}, {'/Bed/red', '/Bed/yellow'})
        self.assert_candidate_geometry(candidates, self.points)

    def test_rotated_translated_map_registration_preserves_map_placements(self) -> None:
        transform = pose(8., -4., .2, .63)
        world_points = (np.c_[self.points, np.ones(2)] @ np.linalg.inv(transform).T)[:, :3]
        expected, actual = self.placements(), self.placements(T_map_world=transform, positions=world_points)
        self.assertEqual(len(expected), len(actual))
        for before, after in zip(expected, actual):
            np.testing.assert_allclose([after['x'], after['y'], after['yaw']], [before['x'], before['y'], before['yaw']])
            np.testing.assert_allclose(transform @ after['T_world_base'], before['T_world_base'], atol=1e-12)
        self.assert_candidate_geometry(actual, world_points)

    def test_minimum_home_distance_can_require_off_center_alignment(self) -> None:
        # root X=.28은 HOME 정면에서는 너무 가까워 허용된 가로 변위가 필요하다.
        point = (pose(2.5, 1.2, yaw=-math.pi/2.) @ self.mount @ np.array([.28, 0., .274, 1.]))[:3]
        candidates = self.placements(positions=np.array([point, self.points[1]]))
        west = [item for item in candidates if item['section_id'] == 'WEST' and item['source_target_id'] == '/Bed/red']
        self.assertEqual(len(west), 2)
        self.assertTrue(all(abs(item['y']-1.2) > .03 for item in west))
        self.assert_candidate_geometry(candidates, np.array([point, self.points[1]]))

    def test_detached_attempted_green_and_wrong_bed_are_excluded(self) -> None:
        self.assertEqual(self.placements(attached=np.zeros(2, dtype=bool)), [])
        self.assertEqual(self.placements(excluded_ids={'/Bed/red', '/Bed/yellow'}), [])
        records = [dict(self.records[0], color='green'), dict(self.records[1], prim_path='/BedOther/yellow')]
        self.assertEqual(self.placements(records=records), [])

    def test_unreachable_height_and_outside_route_have_no_candidates(self) -> None:
        self.assertEqual(self.placements(positions=self.points+[0., 0., 3.]), [])
        self.assertEqual(self.placements(positions=self.points+[0., 20., 0.]), [])
        self.assertEqual(self.placements(records=[], positions=np.empty((0, 3)), attached=np.empty(0, dtype=bool)), [])

    def test_clearance_callback_rejects_candidates_before_selection(self) -> None:
        seen = []

        def clear(candidate: dict) -> bool:
            seen.append(candidate)
            return candidate['section_id'] == 'EAST'

        candidates = self.placements(pose_is_clear=clear)
        self.assertGreater(len(seen), len(candidates))
        self.assertEqual({item['section_id'] for item in candidates}, {'EAST'})

    def test_malformed_shapes_and_reflections_fail_explicitly(self) -> None:
        for change in (dict(positions=np.zeros((1, 3))), dict(attached=np.ones((2, 1))),
                       dict(T_map_world=np.diag([-1., 1., 1., 1.])), dict(base_z_map=float('nan'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.placements(**change)


class FootprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = np.ones((100, 100), dtype=bool)
        self.footprint = np.array([[-.3, -.2], [.3, -.2], [.3, .2], [-.3, .2]])

    def clear(self, **changes: object) -> bool:
        arguments = dict(free_cells=self.grid, resolution=.1, origin=[0., 0., 0.],
                         footprint=self.footprint, pose_xy_yaw=[5., 5., 0.], padding_m=.02)
        arguments.update(changes)
        return footprint_is_clear(**arguments)

    def test_obstacle_inside_body_and_border_cells_are_rejected(self) -> None:
        self.assertTrue(self.clear())
        self.grid[50, 50] = False
        self.assertFalse(self.clear())
        self.grid[50, 50] = True
        self.grid[50, 53] = False
        self.assertFalse(self.clear())
        self.grid[50, 53] = True
        self.grid[55, 55] = False
        self.assertTrue(self.clear())

    def test_rotated_footprint_and_map_origin_follow_same_physical_cells(self) -> None:
        angle = .61
        position = (pose(2., -3., yaw=angle) @ np.array([5., 5., 0., 1.]))[:2]
        kwargs = dict(origin=[2., -3., angle], pose_xy_yaw=[*position, angle])
        self.assertTrue(self.clear(**kwargs))
        self.grid[50, 50] = False
        self.assertFalse(self.clear(**kwargs))

    def test_outside_unknown_and_invalid_grid_are_rejected(self) -> None:
        self.assertFalse(self.clear(pose_xy_yaw=[.1, 5., 0.]))
        self.assertFalse(self.clear(free_cells=np.zeros((100, 100), dtype=bool)))
        with self.assertRaises(ValueError):
            self.clear(free_cells=np.ones((100, 100), dtype=np.uint8))


if __name__ == '__main__':
    unittest.main()
