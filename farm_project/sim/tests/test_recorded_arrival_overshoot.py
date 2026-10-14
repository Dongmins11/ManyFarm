"""실제 시뮬 도착 기록을 공통 Navigator에 재생한다. 물리·Nav2 재실행은 아니다."""
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/farm_navigation'))
sys.path.insert(0, str(ROOT / 'robot/ros_ws/src/harvest_robot'))
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.configuration import load_environment
from farm_navigation.navigator import Navigator
from farm_navigation.route import RouteGraph
from harvest_robot.corridor_navigation import CorridorNavigator, load_corridors
from harvest_robot.staged_navigation import StagedNavigation, load_sections
from harvest_robot.configuration import load_harvest_config


def pose(actual: dict) -> np.ndarray:
    """기록된 map 자세를 TF 대역으로만 사용한다. 제어 입력 주입 시험이 아니다."""
    transform = np.eye(4)
    c, s = math.cos(actual['yaw']), math.sin(actual['yaw'])
    transform[:2, :2] = [[c, -s], [s, c]]
    transform[:2, 3] = [actual['x'], actual['y']]
    return transform


class RecordedArrivalOvershootTests(unittest.TestCase):
    def test_recorded_residuals_remain_visible_without_blocking_next_request(self) -> None:
        """기존 성공3/오차초과3건의 측정값은 보존하되 잔차만으로 다음 이동을 막지 않는다."""
        evidence = json.loads((ROOT / 'sim/docs/changes/DRIVE_BACKEND_REPEAT_20261014.json').read_text())
        profile = load_environment(ROOT / 'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml',
                                   ROOT, 'sim', require_survey=False)
        # 경로 생성은 이번 재생 범위 밖이다. Nav2 반환 이후 공통 종료 경계를 검사한다.
        # 증거 기록 당시의 허용치를 명시해 잔차 초과/비차단 회귀를 재생한다.
        settings = NavigationSettings.from_mapping(dict(
            profile['navigation'], mode='navigate_to_pose', parallel_approach=False,
            arrival_tolerance_m=.02, heading_tolerance_rad=.05))
        self.assertEqual(settings.arrival_tolerance_m, .02)
        self.assertEqual(settings.heading_tolerance_rad, .05)
        expected = {'cpu_01': False, 'cpu_02': True, 'cpu_03': False,
                    'gpu_01': True, 'gpu_02': True, 'gpu_03': False}
        self.assertEqual({item['case'] for item in evidence['results']}, set(expected))
        for item in evidence['results']:
            with self.subTest(case=item['case']):
                arrival = item['navigation'][0]
                goal, actual = arrival['goal_map'], arrival['actual_map']
                stamp = arrival['stamp_ns']
                transform = pose(actual)
                events = []

                def execute(*args) -> int:
                    events.append('nav2_success')
                    return 4

                def wait_stopped(check) -> int:
                    events.append('stopped')
                    return stamp

                def lookup(map_frame, base_frame, requested_stamp, check):
                    self.assertEqual(events[-2:], ['nav2_success', 'stopped'])
                    self.assertEqual(requested_stamp, stamp)
                    events.append('stopped_pose')
                    return transform

                client = NS(has_goal=False, execute=execute)
                records = []
                node = Mock()
                navigator = Navigator(node, settings, client, NS(lookup=lookup),
                    NS(wait_stopped=wait_stopped), lambda: None, record=records.append)
                target = (goal['x'], goal['y'])
                result = navigator.navigate(target, goal['yaw'])
                self.assertEqual(navigator.status.phase, 'ARRIVED')
                self.assertEqual(result.stamp_ns, stamp)
                self.assertEqual(result.measurement['accepted'], expected[item['case']])
                for key in ('position_error_m', 'heading_error_rad'):
                    self.assertAlmostEqual(result.measurement[key], arrival[key])
                    self.assertAlmostEqual(records[0][key], arrival[key])
                self.assertEqual(records[0]['status'], 'ARRIVED')
                self.assertEqual(records[0]['accepted'], expected[item['case']])
                # 후속 목표는 이전 목표보다 진행 방향으로 30cm 앞이다.
                next_goal = (target[0] + .3 * math.cos(goal['yaw']),
                             target[1] + .3 * math.sin(goal['yaw']))
                transform = pose(dict(x=next_goal[0], y=next_goal[1], yaw=goal['yaw']))
                second = navigator.navigate(next_goal, goal['yaw'])
                self.assertTrue(second.measurement['accepted'])
                self.assertEqual(navigator.status.phase, 'ARRIVED')
                self.assertEqual(events, ['nav2_success', 'stopped', 'stopped_pose'] * 2)

    def test_cpu_work_residual_allows_next_forward_window_without_reapproach(self) -> None:
        """실제26.82mm 작업 잔차 뒤 공통 실행기와 수확 단계기가 다음 Window를 실행한다."""
        evidence = json.loads((ROOT / 'sim/docs/changes/STOPPED_ARRIVAL_FIX_20261014.json').read_text())
        trial = next(item for item in evidence['full_mission_trials'] if item['case'] == 'cpu_brake_01')
        arrival = trial['navigation'][1]
        goal, actual = arrival['goal_map'], arrival['actual_map']
        profile = load_environment(ROOT / 'sim/ros_ws/src/farm_sim_config/config/harvest_runtime.yaml',
                                   ROOT, 'sim', require_survey=False)
        settings = NavigationSettings.from_mapping(dict(
            profile['navigation'], arrival_tolerance_m=.02, heading_tolerance_rad=.05))
        config = load_harvest_config(ROOT / 'sim/ros_ws/src/farm_sim_config/config/harvest_task.json', ROOT)
        graph = RouteGraph(ROOT / profile['route_graph'])
        sections = load_sections(config, graph)
        current = pose(dict(x=sections['SEC01'].entry[0], y=sections['SEC01'].entry[1], yaw=goal['yaw']))
        next_goal = (goal['x'] + .3 * math.cos(goal['yaw']), goal['y'] + .3 * math.sin(goal['yaw']))
        stopped = iter((pose(actual), pose(dict(x=next_goal[0], y=next_goal[1], yaw=goal['yaw']))))

        def lookup(*args):
            nonlocal current
            current = next(stopped)
            return current

        from builtin_interfaces.msg import Time
        node = Mock()
        node.get_clock.return_value.now.return_value.to_msg.return_value = Time()
        poses = NS(current=lambda check: current, lookup=lookup)
        client = Mock(has_goal=False)
        client.execute.return_value = 4
        records, phases = [], []
        work = CorridorNavigator(node, settings, client, poses,
            NS(wait_stopped=lambda check: arrival['stamp_ns']), lambda: None, graph,
            records.append, corridors=load_corridors(config, graph))
        approach = Mock()
        staged = StagedNavigation(approach, work, sections,
            lambda: tuple(current[:2, 3]), lambda: None, phases.append, .1,
            resume_current=work.resume_current)

        first = staged.navigate('SEC01', (goal['x'], goal['y']), goal['yaw'])
        self.assertFalse(first.measurement['accepted'])
        self.assertAlmostEqual(first.measurement['position_error_m'], .02681675976067816)
        self.assertEqual(work.status.phase, 'ARRIVED')
        self.assertEqual(staged.current_section, 'SEC01')
        second = staged.navigate('SEC01', next_goal, goal['yaw'])
        self.assertTrue(second.measurement['accepted'])
        self.assertEqual(client.execute.call_count, 2)
        approach.navigate.assert_not_called()
        self.assertEqual([entry['phase'] for entry in phases],
                         ['SECTION_RESUME', 'WINDOW_MOVE'] * 2)
        self.assertEqual([entry['accepted'] for entry in records], [False, True])
        self.assertEqual([entry['status'] for entry in records], ['ARRIVED', 'ARRIVED'])
        self.assertEqual(client.execute.call_args_list[1].args[0], next_goal)
        second_path = client.execute.call_args_list[1].args[2]
        self.assertAlmostEqual(second_path.poses[0].pose.position.x, actual['x'])
        self.assertAlmostEqual(second_path.poses[0].pose.position.y, actual['y'])

    def test_execution_stop_and_tf_failures_still_require_cleanup(self) -> None:
        """측정된 잔차와 달리 실제 실행/정지/자세 조회 실패는 다음 이동을 허용하지 않는다."""
        for failure in ('nav2', 'stop', 'tf'):
            with self.subTest(failure=failure):
                client = Mock(has_goal=False)
                client.execute.return_value = 4
                motion = Mock()
                motion.wait_stopped.return_value = 100
                poses = Mock()
                poses.lookup.return_value = np.eye(4)
                failing = {'nav2': client.execute, 'stop': motion.wait_stopped, 'tf': poses.lookup}[failure]
                successful = {'nav2': 4, 'stop': 100, 'tf': np.eye(4)}[failure]
                # stop 실패 뒤 cleanup과 새 요청에 각각 정지 확인이 필요하다.
                failing.side_effect = [RuntimeError(failure + ' failed'), successful, successful]
                nav = Navigator(Mock(), NavigationSettings(), client, poses, motion, lambda: None)
                with self.assertRaisesRegex(RuntimeError, failure + ' failed'):
                    nav.navigate((0., 0.), 0.)
                self.assertEqual(nav.status.phase, 'INTERRUPTED')
                calls = client.execute.call_count
                with self.assertRaisesRegex(RuntimeError, '종료·정지 확인'):
                    nav.navigate((0., 0.), 0.)
                self.assertEqual(client.execute.call_count, calls)
                nav.cancel_nav()
                client.cancel.assert_called_once()
                self.assertEqual(nav.status.phase, 'STOPPED')
                self.assertTrue(nav.navigate((0., 0.), 0.).measurement['accepted'])


if __name__ == '__main__':
    unittest.main()
