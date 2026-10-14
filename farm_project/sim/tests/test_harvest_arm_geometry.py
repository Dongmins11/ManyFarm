"""실제 URDF·공통 예찰 계산·시뮬 평가의 오른팔 좌표 계약을 ROS/Isaac 없이 검사합니다."""
from __future__ import annotations

from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
for tree, package in [('robot', 'scout_robot'), ('robot', 'farm_navigation'), ('sim', 'farm_sim_harvest')]:
    sys.path.insert(0, str(ROOT / tree / 'ros_ws/src' / package))
sys.path.insert(0, str(ROOT / 'sim/tools'))
from farm_navigation.arrival import measure_arrival, validate_goal_checkers
from farm_navigation.configuration import load_environment, load_nav2_parameters
from farm_navigation.route import RouteGraph, load_route
from farm_sim_harvest.evaluation import count_snapshot
from scout_robot.survey_core import StraightBed, Survey
from rebuild_route_data import build


def rigid_transform(xyz: list[float], rpy: list[float]) -> np.ndarray:
    """URDF의 xyz(m), RPY(rad)를 부모←자식 동차 변환으로 반환합니다."""
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    transform = np.eye(4)
    transform[:3, :3] = [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr]]
    transform[:3, 3] = xyz
    return transform


def urdf_arm_mount() -> np.ndarray:
    """자산 URDF의 고정 joint 체인을 따라 논리 base_footprint←arm_2를 구합니다."""
    source = ROOT / 'sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf'
    joints = {joint.find('child').attrib['link']: joint for joint in ET.parse(source).findall('joint')}
    chain = []
    child = 'arm_2/base_link'
    while child != 'base_footprint':
        joint = joints[child]
        if joint.attrib['type'] != 'fixed':
            raise AssertionError('팔 장착점까지의 체인은 고정 joint여야 합니다.')
        origin = joint.find('origin')
        chain.append(rigid_transform(
            list(map(float, origin.attrib.get('xyz', '0 0 0').split())),
            list(map(float, origin.attrib.get('rpy', '0 0 0').split()))))
        child = joint.find('parent').attrib['link']
    device = json.loads((CONFIG / 'harvest.json').read_text())
    transform = rigid_transform([0, 0, 0], [0, 0, -device['scene_binding']['control_frame_yaw_rad']])
    for item in reversed(chain):
        transform = transform @ item
    return transform


class HarvestArmGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.survey = json.loads((CONFIG / 'scout_survey.json').read_text())
        cls.workspace = json.loads((CONFIG / 'harvest_audit.json').read_text())['evaluation']['workspace']

    def test_urdf_mount_and_full_root_envelope_match_audit(self) -> None:
        """정책의 과실 root 외곽 8점을 실제 팔 장착 TF로 변환해 평가 상자와 비교합니다."""
        transform = urdf_arm_mount()
        np.testing.assert_allclose(transform[:3, 3], [.19, .185, .713], atol=1e-12)
        np.testing.assert_allclose(transform[:3, :3] @ [1, 0, 0], [0, 1, 0], atol=1e-12)
        corners = np.array(list(itertools.product((.265, .365), (-.175, .175), (-.1, .35))))
        local = corners @ transform[:3, :3].T + transform[:3, 3]
        center, size = np.array(self.workspace['center_m']), np.array(self.workspace['size_m'])
        np.testing.assert_allclose(local.min(axis=0), center - size / 2, atol=1e-12)
        np.testing.assert_allclose(local.max(axis=0), center + size / 2, atol=1e-12)

    def test_sensor_window_goal_matches_audit_for_all_sections(self) -> None:
        """16구역의 합성 센서 좌표로 생성한 Goal과 평가 상자 8꼭짓점을 대조합니다."""
        for section_id, section in self.survey['sections'].items():
            with self.subTest(section=section_id):
                bed = StraightBed(load_route(ROOT / section['route_file'], section['node_ids']), section)
                survey = Survey(bed, section_id, .065)
                observation = bed.world(bed.length / 2, bed.bed_n, .838)
                survey.ingest([dict(position_map_m=observation, class_name='red', confidence=.9, stamp_ns=1)])
                window, = survey.windows()
                goal = window['goal_pose']
                transform = rigid_transform(goal['position'], [0, 0, goal['yaw']])
                world_corners = np.asarray(window['corners_map_m'])
                local = (world_corners - transform[:3, 3]) @ transform[:3, :3]
                center, size = np.array(self.workspace['center_m']), np.array(self.workspace['size_m'])
                np.testing.assert_allclose(local.min(axis=0), center - size / 2, atol=1e-12)
                np.testing.assert_allclose(local.max(axis=0), center + size / 2, atol=1e-12)
                snapshot = dict(complete=True, T_world_base=transform.tolist(), stamp_ns=1, scene_session='fixture',
                                fruits=[dict(gt_id='fixture', class_name='red', center_world_m=observation)])
                audit = count_snapshot(snapshot, self.workspace, 1, set())
                self.assertEqual(audit['actual_in_workspace'], 1)

    def test_same_observation_shifts_goal_without_changing_heading(self) -> None:
        """같은 Window의 Goal은 주행방향 -38cm, 베드 반대쪽 -6.5cm만큼 바뀝니다."""
        for section_id, section in self.survey['sections'].items():
            with self.subTest(section=section_id):
                route = load_route(ROOT / section['route_file'], section['node_ids'])
                before = deepcopy(section)
                before['harvest'].update(mount_xy_base_m=[-.19, .185],
                                         work_offset_xy_base_m=[0, .25], height_reference_m=.703)
                beds = [StraightBed(route, item) for item in (before, section)]
                windows = []
                for bed in beds:
                    survey = Survey(bed, section_id, .065)
                    survey.ingest([dict(position_map_m=bed.world(bed.length / 2, bed.bed_n, .838),
                                        class_name='red', confidence=.9, stamp_ns=1)])
                    window, = survey.windows()
                    windows.append(window)
                old, new = windows
                delta = np.array(new['goal_pose']['position'])[:2] - np.array(old['goal_pose']['position'])[:2]
                np.testing.assert_allclose(delta, -.38 * beds[1].t - .065 * beds[1].n, atol=1e-12)
                self.assertAlmostEqual(new['goal_pose']['yaw'], old['goal_pose']['yaw'])
                self.assertEqual(new['expected_count'], old['expected_count'])

    def test_generated_survey_and_audit_use_same_task_source(self) -> None:
        """task.yaml 재생성 뒤에도 예찰·수확 평가 설정이 서로 어긋나지 않습니다."""
        outputs = build()
        for name in ('scout_survey.json', 'harvest_audit.json'):
            self.assertEqual(outputs[f'config/{name}'], json.loads((CONFIG / name).read_text()))
        task = yaml.safe_load((CONFIG / 'task.yaml').read_text())
        self.assertEqual(set(task['sections']), set(self.survey['sections']))

    def test_work_goals_stay_on_route_and_preserve_exact_endpoint(self) -> None:
        """현 작업선 위 목표의 끝점 보존과 마지막 주행 선분의 정적 지도 ray를 검사합니다."""
        profile = load_environment(CONFIG / 'harvest_runtime.yaml', ROOT, 'sim', require_survey=False)
        nav = profile['navigation']
        graph = RouteGraph(ROOT / profile['route_graph'])
        task = yaml.safe_load((CONFIG / 'task.yaml').read_text())
        station = tuple(task['stations']['harvest_01']['xy_m'])
        map_path = ROOT / profile['map_yaml']
        map_config = yaml.safe_load(map_path.read_text())
        with Image.open(map_path.parent / map_config['image']) as image:
            pixels = np.array(image.convert('L'))
        origin = rigid_transform([*map_config['origin'][:2], 0], [0, 0, map_config['origin'][2]])
        for section_id, section in self.survey['sections'].items():
            bed = StraightBed(load_route(ROOT / section['route_file'], section['node_ids']), section)
            for along in (.5, bed.length / 2, bed.length - .5):
                with self.subTest(section=section_id, along=along):
                    survey = Survey(bed, section_id, .065)
                    survey.ingest([dict(position_map_m=bed.world(along, bed.bed_n, .838),
                                        class_name='red', confidence=.9, stamp_ns=1)])
                    window, = survey.windows()
                    goal = window['goal_pose']
                    target = tuple(goal['position'][:2])
                    path = graph.plan(station, target, nav['max_start_distance_m'], nav['max_goal_distance_m'])
                    self.assertEqual(path.points[-1], target)
                    a, b = np.array(path.points[-2]), np.array(path.points[-1])
                    # 오른팔 목표와 작업선은 이미 정렬되어 있어 별도 6cm 횡연결이 없다.
                    self.assertAlmostEqual(min(item[1] for item in graph._candidates(
                        target, nav['max_goal_distance_m'])), 0.)
                    self.assertAlmostEqual(float((b - a) @ bed.n), 0.)
                    self.assertGreater(float((b - a) @ bed.t), 0.)
                    # 5mm 간격의 centerline 검사이며 로봇 footprint/실시간 장애물 인증은 아닙니다.
                    samples = math.ceil(float(np.linalg.norm(b - a)) / .005) + 1
                    for ratio in np.linspace(0, 1, samples):
                        world = np.r_[a + ratio * (b - a), 0]
                        local = origin[:3, :3].T @ (world - origin[:3, 3])
                        col, row_from_bottom = np.floor(local[:2] / map_config['resolution']).astype(int)
                        row = pixels.shape[0] - 1 - row_from_bottom
                        self.assertTrue(0 <= row < pixels.shape[0] and 0 <= col < pixels.shape[1])
                        gray = float(pixels[row, col]) / 255
                        occupancy = gray if map_config['negate'] else 1 - gray
                        self.assertLess(occupancy, map_config['free_thresh'])
                    upstream_pose = rigid_transform([*a, 0], [0, 0, goal['yaw']])
                    arrival = measure_arrival(upstream_pose, target, goal['yaw'],
                                              nav['arrival_tolerance_m'], nav['heading_tolerance_rad'])
                    self.assertFalse(arrival['accepted'])

    def test_goal_checker_is_stricter_than_arrival_and_has_no_deadband(self) -> None:
        """Nav2 사전검사 계약과 수확 전용 정밀 도착 설정을 함께 검사합니다."""
        nav = load_environment(CONFIG / 'harvest_runtime.yaml', ROOT, 'sim', require_survey=False)['navigation']
        controller = load_nav2_parameters(CONFIG / 'nav2_harvest.yaml', ROOT)
        parameters = controller['controller_server']['ros__parameters']
        flat = {'goal_checker_plugins': parameters['goal_checker_plugins']}
        for name in parameters['goal_checker_plugins']:
            flat.update({f'{name}.{key}': value for key, value in parameters[name].items()})
        self.assertTrue(validate_goal_checkers(flat, nav['arrival_tolerance_m'], nav['heading_tolerance_rad']))
        checker = parameters[nav['goal_checker_id']]
        self.assertEqual(checker['plugin'], 'nav2_controller::SimpleGoalChecker')
        self.assertIs(checker['stateful'], True)
        for name in ('HarvestApproach', 'HarvestWork'):
            self.assertIn(name, parameters['controller_plugins'])
            self.assertEqual(parameters[name]['plugin'],
                             'nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController')
            self.assertTrue(parameters[name]['use_fixed_curvature_lookahead'])
            self.assertTrue(parameters[name]['interpolate_curvature_after_goal'])
            self.assertEqual(parameters[name]['curvature_lookahead_dist'], .4)
        self.assertLess(nav['arrival_tolerance_m'], .06)
        self.assertEqual(controller['velocity_smoother']['ros__parameters']['deadband_velocity'], [0, 0, 0])
        # 20Hz에서 최소 접근속도 0.05m/s의 1step 이동량은 2.5mm로 40mm gate보다 작습니다.
        step = parameters['RPP']['min_approach_linear_velocity'] / parameters['controller_frequency']
        self.assertLess(step, checker['xy_goal_tolerance'])

    def test_device_clocks_and_vision_crop_match_physics_workspace(self) -> None:
        """단독/통합 장치 주기와 예찰 크롭이 같은 물리·오른팔 프로파일을 사용합니다."""
        physics_path = 'sim/ros_ws/src/farm_sim_config/config/robotarm_physics.json'
        physics = json.loads((ROOT / physics_path).read_text())
        self.assertEqual(physics['fruit']['mass_kg'], physics['stem']['mass'])
        self.assertEqual(physics['physics_hz'] % physics['render_hz'], 0)
        self.assertEqual(physics['physics_hz'] % physics['control_hz'], 0)
        for robot in ('scout', 'scout_fleet', 'harvest'):
            runtime = json.loads((CONFIG / f'{robot}.json').read_text())['runtime']
            self.assertEqual(runtime['robotarm_physics_config'], physics_path)
            self.assertEqual(runtime['physics_hz'], physics['physics_hz'])
            self.assertEqual(runtime['render_hz'], physics['render_hz'])
        center, size = self.workspace['center_m'][2], self.workspace['size_m'][2]
        crop = json.loads((CONFIG / 'scout_vision.json').read_text())['preprocess']['height_band_m']
        np.testing.assert_allclose(crop, [center - size / 2, center + size / 2], atol=1e-12)


if __name__ == '__main__':
    unittest.main()
