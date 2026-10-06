"""station 좌표 변환과 시작 설정 검증. Isaac 물리 실행을 대체하지 않습니다."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.station_spawn import read_station, station_transforms, verify_station_pose


def transform(x: float, y: float, z: float, yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0, x], [s, c, 0, y], [0, 0, 1, z], [0, 0, 0, 1.]])


class StationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_dir = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
        self.device = json.loads((self.config_dir / 'scout.json').read_text())
        self.station = read_station(self.config_dir / 'scout.json', self.device)

    def test_shared_station_and_amcl(self) -> None:
        task = yaml.safe_load((self.config_dir / 'task.yaml').read_text())
        source = task['stations'][self.device['robot_id']]
        nav = yaml.safe_load((self.config_dir / 'nav2_scout.yaml').read_text())
        amcl = nav['amcl']['ros__parameters']
        self.assertEqual(self.station['xy_m'], source['xy_m'])
        self.assertEqual(amcl['initial_pose'], dict(x=source['xy_m'][0], y=source['xy_m'][1],
                                                  z=0., yaw=source['yaw_rad']))
        self.assertTrue(amcl['set_initial_pose'])

    def test_parent_body_offsets_and_registration(self) -> None:
        # 회전된 부모, body의 로컬 오프셋, 비영점 map/world 등록을 동시에 검사합니다.
        station = dict(self.station, T_map_world=transform(3, -4, .7, .4).tolist())
        parent = transform(2, 3, .2, .8)
        root = parent @ transform(1, -2, .3, -.5)
        body_local = transform(.12, -.04, .08, .2)
        body = root @ body_local
        local, desired = station_transforms(station, body, root, parent)
        actual_body = parent @ local @ body_local
        np.testing.assert_allclose(actual_body, desired, atol=1e-10)
        map_pose = np.array(station['T_map_world']) @ actual_body
        np.testing.assert_allclose(map_pose[:2, 3], station['xy_m'], atol=1e-10)
        self.assertAlmostEqual(map_pose[2, 3], (np.array(station['T_map_world']) @ body)[2, 3])
        self.assertAlmostEqual(math.atan2(map_pose[1, 0], map_pose[0, 0]), station['yaw_rad'])
        second, _ = station_transforms(station, actual_body, parent @ local, parent)
        np.testing.assert_allclose(second, local, atol=1e-10)

    def test_post_physics_verification(self) -> None:
        station = self.station
        yaw = station['yaw_rad']
        quaternion = [math.cos(yaw/2), 0, 0, math.sin(yaw/2)]
        verify_station_pose(station, [*station['xy_m'], .08], quaternion)
        with self.assertRaises(RuntimeError):
            verify_station_pose(station, [0, 0, .08], quaternion)
        with self.assertRaises(RuntimeError):
            verify_station_pose(station, [*station['xy_m'], .08], [1, 0, 0, 0])

    def test_invalid_registration(self) -> None:
        for bad in (np.diag([2., 1, 1, 1]), np.full((4, 4), np.nan), np.eye(3)):
            with self.assertRaises(ValueError):
                station_transforms(dict(self.station, T_map_world=bad), np.eye(4), np.eye(4), np.eye(4))

    def test_invalid_station_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.json'
            output = path.parent / 'station_spawn.json'
            data = json.loads((self.config_dir / 'station_spawn.json').read_text())
            for bad in ('wrong_map', 'unknown_yaw', 'proposed'):
                copy = json.loads(json.dumps(data))
                if bad == 'wrong_map': copy['map_id'] = 'other'
                if bad == 'unknown_yaw': copy['stations']['scout_01']['yaw_rad'] = None
                if bad == 'proposed': copy['stations']['scout_01']['status'] = 'DESIGN_PROPOSAL'
                output.write_text(json.dumps(copy))
                with self.assertRaises(ValueError): read_station(path, self.device)
            device = dict(self.device, station_spawn=dict(enabled=True, config='../outside.json'))
            with self.assertRaises(ValueError): read_station(path, device)

    def test_opt_out(self) -> None:
        device = dict(self.device, station_spawn={'enabled': False})
        self.assertIsNone(read_station(self.config_dir / 'scout.json', device))


if __name__ == '__main__':
    unittest.main()
