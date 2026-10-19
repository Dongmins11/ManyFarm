"""PC 오프라인: 공통 팔 설정 선택, 좌표 전체 작업 대기와 이동 허용 경계."""
from dataclasses import dataclass
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as S
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_robot.arm_client import configured_arm_settings
from harvest_robot.mission import HarvestMission, MissionCanceled


@dataclass
class Arrival:
    stamp_ns: int = 1


class ArmConnectionTests(unittest.TestCase):
    def test_same_settings_for_real_and_sim(self):
        for mode in ('real', 'sim'):
            settings = configured_arm_settings(dict(mode=mode, completion_policy='ARRIVAL_THEN_ARM',
                arm_action=dict(endpoint='/test_only/arm', execution_timeout_s=12.)))
            self.assertEqual(settings.endpoint, '/test_only/arm')
            self.assertEqual(settings.execution_timeout_s, 12.)

    def test_arrival_only_does_not_need_or_select_arm(self):
        self.assertIsNone(configured_arm_settings(dict(completion_policy='ARRIVAL_ONLY_NO_HARVEST')))

    def test_missing_contract_is_not_replaced_with_sim_endpoint(self):
        for arm in (None, {}, {'endpoint': ''}):
            with self.subTest(arm=arm), self.assertRaises(ValueError):
                configured_arm_settings(dict(completion_policy='ARRIVAL_THEN_ARM', arm_action=arm))
        with self.assertRaises(ValueError):
            configured_arm_settings(dict(completion_policy='unknown'))

    def fixture(self, execute, cancel=lambda: None):
        events = []
        node = S(check=lambda: None, config={}, arm_result=None, arm_travel_ready=True,
            navigator=S(preflight_navigation=lambda: None,
                navigate=lambda *_: (events.append('arrival') or Arrival()), cancel_nav=lambda: None),
            arm_client=S(execute=execute, has_goal=True, cancel=cancel),
            communication=S(arm_feedback=lambda a,b: events.append((a,b))))
        goal = S(harvest_task=S(goal_pose=S(position=S(x=1.,y=2.),yaw=0.)))
        return node, goal, events

    def test_each_attempt_feedback_does_not_finish_coordinate(self):
        waiting, finish = threading.Event(), threading.Event()
        def execute(goal, check, progress):
            for counts in ((1,0),(1,1),(2,1)):
                progress(*counts)
            waiting.set()
            if not finish.wait(2.):
                raise RuntimeError('test terminal not supplied')
            return dict(result_code='SUCCESS')
        node, goal, events = self.fixture(execute)
        errors = []
        def run():
            try: HarvestMission(node,goal).run()
            except Exception as error: errors.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(waiting.wait(1.))
            self.assertTrue(worker.is_alive())
            self.assertFalse(node.arm_travel_ready)
            self.assertEqual(events,['arrival',(1,0),(1,1),(2,1)])
        finally:
            finish.set();worker.join(2.)
        self.assertFalse(errors)
        self.assertFalse(worker.is_alive())
        self.assertTrue(node.arm_travel_ready)

    def test_failed_terminal_does_not_confirm_folded_pose(self):
        node,goal,_ = self.fixture(lambda *_: dict(result_code='FAILED'))
        HarvestMission(node,goal).run()
        self.assertFalse(node.arm_travel_ready)

    def test_cancel_terminal_does_not_confirm_folded_pose(self):
        def execute(*_): raise MissionCanceled('cancel')
        node,goal,_ = self.fixture(execute, lambda: dict(result_code='CANCELED'))
        with self.assertRaises(MissionCanceled): HarvestMission(node,goal).run()
        self.assertFalse(node.arm_travel_ready)
        self.assertEqual(node.arm_result['result_code'],'CANCELED')


if __name__ == '__main__': unittest.main()
