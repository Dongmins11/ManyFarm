"""현장 프로파일의 ROI 의미와 주행 설정 보존을 검증한다. 실물 주행 시험은 아니다."""
import math
from pathlib import Path
import sys
import unittest
import yaml
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from farm_tag_localization.tag_adapter import OBSERVATION_ROI
from farm_tag_localization.roi import roi_accept

class FieldProfile(unittest.TestCase):
    def test_monitor_roi_is_not_correction_roi(self) -> None:
        # 모니터 60x60 하단 576px 밖이지만 보정60x80 하단648px 안이다.
        detection = {'corners': [[480,260],[820,260],[820,600],[480,600]]}
        self.assertFalse(roi_accept(detection,(.6,.6)))
        self.assertTrue(roi_accept(detection,OBSERVATION_ROI))
        detection['corners'][2][1] = 650
        self.assertFalse(roi_accept(detection,OBSERVATION_ROI))

    def test_both_controller_aliases_use_field_profile(self) -> None:
        config = yaml.safe_load((ROOT/'robot/config/robots/vicpinky/nav2.yaml').read_text())
        p = config['controller_server']['ros__parameters']
        for alias in ('FollowPath','RPP'):
            c = p[alias]
            self.assertAlmostEqual(c['rotate_to_heading_min_angle'],math.radians(6))
            self.assertEqual(c['desired_linear_vel'],.1)
            self.assertEqual(c['rotate_to_heading_angular_vel'],.1)
            self.assertTrue(c['use_collision_detection'])
        # 최종 미션 판정은 5cm/3도, Nav2는 정지 후 판정 여유를 둔다.
        environment = yaml.safe_load((ROOT/'robot/config/environments/harvest_real.yaml').read_text())
        self.assertEqual(environment['navigation']['arrival_tolerance_m'], .05)
        self.assertEqual(environment['navigation']['heading_tolerance_rad'], .05236)
        self.assertEqual(p['general_goal_checker']['xy_goal_tolerance'], .04)
        self.assertAlmostEqual(p['general_goal_checker']['yaw_goal_tolerance'], math.radians(2.5))
        self.assertEqual(p['progress_checker']['required_movement_radius'],.1)
        self.assertEqual(p['progress_checker']['movement_time_allowance'],20.)
