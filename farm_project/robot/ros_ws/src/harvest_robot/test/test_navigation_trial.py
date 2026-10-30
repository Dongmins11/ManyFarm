"""팔 없는 실물 이동의 소유권·종료·기존 컴포넌트 재사용 계약 시험."""
import math
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import Mock, patch
from nav2_msgs.action import NavigateToPose
from rclpy.action import GoalResponse
from farm_common.action_handoff import ActionHandoff, ActionInterrupted
from harvest_robot.navigation_trial import NavigationTrial, trial_target

ROOT = Path(__file__).resolve().parents[5]

class TrialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.node = S(lock=threading.RLock(), busy=False, blocked=False, stopping=False,
            handoff=ActionHandoff(), staged_navigation=Mock(), tag_control=Mock(),
            check=Mock(), config={'sections':{'SEC_01':{}}, 'default_section_id':'SEC_01'},
            section_resolution={}, callbacks=Mock(), get_logger=Mock(return_value=Mock()))
        self.prepare = Mock()
        with patch('harvest_robot.navigation_trial.ActionServer'):
            self.server = NavigationTrial(self.node, root=ROOT, profile=dict(mode='real',
                navigation_trial_config='robot/tools/terminal/dinit.json'), prepare=self.prepare)
        self.goal = NavigateToPose.Goal()
        _, xy, yaw, frame = trial_target(ROOT, 'robot/tools/terminal/dinit.json')
        self.goal.pose.header.frame_id=frame
        self.goal.pose.pose.position.x,self.goal.pose.pose.position.y=xy
        self.goal.pose.pose.orientation.z=math.sin(yaw/2)
        self.goal.pose.pose.orientation.w=math.cos(yaw/2)
        self.handle=Mock(request=self.goal,is_cancel_requested=False)

    def test_success_calls_navigation_without_arm(self) -> None:
        self.assertEqual(self.server.accept(self.goal),GoalResponse.ACCEPT)
        result=self.server.execute(self.handle)
        self.assertEqual(result.error_code,0)
        self.handle.succeed.assert_called_once()
        self.prepare.assert_called_once()
        _, xy, yaw, _ = trial_target(ROOT, 'robot/tools/terminal/dinit.json')
        self.node.staged_navigation.navigate.assert_called_once_with('SEC_01',xy,yaw)
        self.node.tag_control.end.assert_called_once()
        self.assertFalse(self.node.busy or self.node.handoff.busy)

    def test_goal_cannot_override_config(self) -> None:
        self.goal.pose.pose.position.x+=1
        self.assertEqual(self.server.accept(self.goal),GoalResponse.REJECT)
        self.assertFalse(self.node.handoff.busy)

    def test_busy_does_not_preempt(self) -> None:
        self.node.handoff.reserve('station','existing')
        self.assertEqual(self.server.accept(self.goal),GoalResponse.REJECT)
        self.assertFalse(self.node.handoff.work_interrupted)

    def test_cancel_before_execute_releases_reservation(self) -> None:
        self.server.accept(self.goal)
        self.handle.is_cancel_requested=True
        self.server.cancel(self.handle)
        self.server.execute(self.handle)
        self.handle.canceled.assert_called_once()
        self.node.staged_navigation.navigate.assert_not_called()
        self.assertFalse(self.node.busy or self.node.handoff.busy)

    def test_cancel_during_navigation_uses_existing_check(self) -> None:
        self.server.accept(self.goal)
        def navigate(*args):
            self.handle.is_cancel_requested=True
            self.server.cancel(self.handle)
            self.assertTrue(self.node.handoff.work_interrupted)
            raise ActionInterrupted('취소')
        self.node.staged_navigation.navigate.side_effect=navigate
        self.server.execute(self.handle)
        self.handle.canceled.assert_called_once()
        self.node.staged_navigation.cancel_nav.assert_called_once()
        self.assertFalse(self.node.handoff.busy)

    def test_prepare_failure_does_not_start_or_clear_error(self) -> None:
        self.prepare.side_effect=RuntimeError('ARM_TRAVEL_NOT_READY')
        self.server.accept(self.goal)
        result=self.server.execute(self.handle)
        self.handle.abort.assert_called_once()
        self.assertNotEqual(result.error_code,0)
        self.node.staged_navigation.navigate.assert_not_called()
        self.assertFalse(self.node.busy or self.node.handoff.busy)

    def test_unconfirmed_stop_blocks_and_aborts(self) -> None:
        self.node.staged_navigation.cancel_nav.side_effect=RuntimeError('정지 미확인')
        self.server.accept(self.goal)
        result=self.server.execute(self.handle)
        self.assertTrue(self.node.blocked)
        self.assertIn('CANCEL_UNCONFIRMED',result.error_msg)
        self.handle.abort.assert_called_once()
        self.handle.succeed.assert_not_called()

    def test_real_target_matches_existing_work_corridor(self) -> None:
        import json
        from farm_navigation.route import RouteGraph
        from harvest_robot.corridor_navigation import load_corridors
        from harvest_robot.contract import resolve_section
        config=json.loads((ROOT/'robot/config/harvest/harvest_handoff_jetson_real.json').read_text())
        graph=RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
        _,xy,yaw,_=trial_target(ROOT,'robot/tools/terminal/dinit.json')
        section=resolve_section(None,config,S(position=S(x=xy[0],y=xy[1]),yaw=yaw),
            corridors=load_corridors(config,graph))
        self.assertEqual(section,'SEC_01')
