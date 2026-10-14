"""시뮬 장착/배치와 공통 관측기의 연결 검사. 합성 코너이며 실제 렌더·주행 시험이 아니다."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'sim/ros_ws/src/farm_sim_config/config'
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_tag_localization'))
from farm_tag_localization.runtime import load_observer, validate_binding
from farm_tag_localization.tag_adapter import observe


class TagLocalizationIntegration(unittest.TestCase):
    def test_real_render_detector_corners_use_correct_tag_axes(self) -> None:
        fixture = json.loads((Path(__file__).parent / 'fixtures/apriltag_sec01_id104_ros.json').read_text())
        _, observer = load_observer(str(CONFIG / 'tag_localization/harvest.yaml'), str(ROOT), 'render-regression')
        candidate, detail = observe(observer, dict(fixture['record'], section_id=fixture['section_id']))
        self.assertIsNotNone(candidate, detail)
        error = np.array(candidate['q']) - fixture['expected_pose']
        error[2] = math.atan2(math.sin(error[2]), math.cos(error[2]))
        self.assertLess(np.linalg.norm(error[:2]), .005)
        self.assertLess(abs(error[2]), .01)

    def test_generated_files_match_scene_and_map_sources(self) -> None:
        spec = importlib.util.spec_from_file_location('build_tag_localization', ROOT / 'sim/tools/build_tag_localization.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, expected in module.build().items():
            path = CONFIG / name
            actual = yaml.safe_load(path.read_text()) if path.suffix == '.yaml' else json.loads(path.read_text())
            self.assertEqual(actual, expected, name)
        for robot in ('harvest', 'scout'):
            profile = yaml.safe_load((CONFIG / f'tag_localization/{robot}.yaml').read_text())
            environment = yaml.safe_load((CONFIG / f'{robot}_runtime.yaml').read_text())
            validate_binding(profile, environment, ROOT)

    def test_scout_camera_uses_picam_mount_and_preserves_survey_sensor(self) -> None:
        device = json.loads((CONFIG / 'scout.json').read_text())
        fleet = json.loads((CONFIG / 'scout_fleet.json').read_text())
        self.assertEqual(device['tag_camera'], fleet['tag_camera'])
        self.assertEqual(device['camera'], fleet['camera'])
        self.assertEqual((device['camera']['width'], device['camera']['height']), (640, 384))
        self.assertNotEqual(device['camera']['shm_name'], device['tag_camera']['shm_name'])
        urdf = ET.parse(ROOT / 'sim/assets/robots/scout_robot/urdf/turtlebot3_burger.portable.urdf')
        joints = {j.find('child').get('link'): j for j in urdf.findall('joint')}

        def transform(link: str) -> np.ndarray:
            if link == 'base_footprint':
                return np.eye(4)
            joint = joints[link]
            origin = joint.find('origin')
            roll, pitch, yaw = map(float, origin.get('rpy', '0 0 0').split())
            cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch),
                                     math.sin(pitch), math.cos(yaw), math.sin(yaw))
            local = np.eye(4)
            local[:3, :3] = [[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                             [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]]
            local[:3, 3] = list(map(float, origin.get('xyz', '0 0 0').split()))
            return transform(joint.find('parent').get('link')) @ local

        np.testing.assert_allclose(device['tag_camera']['T_base_optical'],
                                   transform('picam_optical_frame'), atol=1e-10)
        _, scout = load_observer(str(CONFIG / 'tag_localization/scout.yaml'), str(ROOT), 'scout-binding')
        _, harvest = load_observer(str(CONFIG / 'tag_localization/harvest.yaml'), str(ROOT), 'harvest-binding')
        self.assertEqual(scout.context.tag_map_version, harvest.context.tag_map_version)
        self.assertNotEqual(scout.context.calibration_version, harvest.context.calibration_version)
        self.assertNotEqual(scout.context.extrinsics_version, harvest.context.extrinsics_version)
        self.assertEqual(scout.camera.optical_frame, device['frames']['tag_camera_optical'])

    def test_scout_tags_fit_image_and_use_shared_observer_on_all_sections(self) -> None:
        _, observer = load_observer(str(CONFIG / 'tag_localization/scout.yaml'), str(ROOT), 'scout-geometry')
        survey = json.loads((CONFIG / 'scout_survey.json').read_text())
        checked = 0
        for section_id, tags in observer.section_landmarks.items():
            geometry = survey['sections'][section_id]['survey_geometry']
            start, end = np.array(geometry['start_xy_m']), np.array(geometry['end_xy_m'])
            yaw = math.atan2(*(end - start)[::-1])
            c, s = math.cos(yaw), math.sin(yaw)
            for (family, tag_id), tag in tags.items():
                with self.subTest(section_id=section_id, tag_id=tag_id):
                    target = np.eye(4)
                    target[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
                    target[0, 3] = start[0]
                    offset = target[:3, :3] @ observer.t_base_camera[:3, 3]
                    target[1, 3] = tag.t_map_tag[1, 3] - offset[1] + .01
                    corners = observer.project_map_base(target, tag)
                    self.assertTrue(np.all(corners >= [0, 0]))
                    self.assertTrue(np.all(corners < [observer.camera.width, observer.camera.height]))
                    record = dict(section_id=section_id, source_stamp_ns=1,
                        frame_id=observer.camera.optical_frame, detections=[dict(
                            family=family, id=tag_id, corners_rectified=corners.tolist(),
                            decision_margin=100.0, hamming=0)])
                    candidate, detail = observe(observer, record)
                    self.assertIsNotNone(candidate, detail)
                    error = np.array(candidate['q']) - [target[0, 3], target[1, 3], yaw]
                    error[2] = math.atan2(math.sin(error[2]), math.cos(error[2]))
                    np.testing.assert_allclose(error, 0.0, atol=1e-7)
                    self.assertEqual(detail['selected']['section_id'], section_id)
                    checked += 1
        self.assertEqual(checked, 240)

    def test_each_registered_tag_recovers_pose_on_its_section_route(self) -> None:
        _, observer = load_observer(str(CONFIG / 'tag_localization/harvest.yaml'), str(ROOT), 'geometry-test')
        survey = json.loads((CONFIG / 'scout_survey.json').read_text())
        placement = json.loads((CONFIG / 'apriltag_map.json').read_text())
        checked = 0
        for section_id, tags in observer.section_landmarks.items():
            route = survey['sections'][section_id]['harvest_route']
            yaw = route['heading_rad']
            c, s = math.cos(yaw), math.sin(yaw)
            for (family, tag_id), tag in tags.items():
                with self.subTest(section_id=section_id, tag_id=tag_id):
                    target = np.eye(4)
                    target[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
                    target[0, 3] = route['x_m']
                    offset = target[:3, :3] @ observer.t_base_camera[:3, 3]
                    # 무잡음 중심 정렬에서는 OpenCV IPPE가 NaN 두 해를 반환할 수 있다.
                    # 실제 코너 회귀는 위 별도 시험으로 확인하고, 전체 배치는 1cm 옆에서 검사한다.
                    target[1, 3] = tag.t_map_tag[1, 3] - offset[1] + .01
                    corners = observer.project_map_base(target, tag)
                    record = dict(section_id=section_id, source_stamp_ns=1,
                        frame_id=observer.camera.optical_frame, detections=[dict(
                            family=family, id=tag_id, corners_rectified=corners.tolist(),
                            decision_margin=100.0, hamming=0)])
                    candidate, detail = observe(observer, record)
                    self.assertIsNotNone(candidate, detail)
                    error = np.array(candidate['q']) - [target[0, 3], target[1, 3], yaw]
                    error[2] = math.atan2(math.sin(error[2]), math.cos(error[2]))
                    np.testing.assert_allclose(error, 0.0, atol=1e-7)
                    self.assertEqual(detail['selected']['section_id'], section_id)
                    checked += 1
        self.assertEqual(checked, len(placement['tags']))
        self.assertEqual(set(observer.section_landmarks), {tag['section_id'] for tag in placement['tags']})


if __name__ == '__main__':
    unittest.main()
