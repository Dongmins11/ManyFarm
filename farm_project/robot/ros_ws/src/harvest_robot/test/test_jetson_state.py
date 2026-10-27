"""PC 오프라인: 상태 재전송·만료·재시작 및 원본 odom 정지 증거를 검증한다."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harvest_robot.jetson_state import JetsonSettings, RuntimeSample, RuntimeTracker, ControlTracker
from harvest_robot.jetson_connection import create_jetson_connection
from types import SimpleNamespace as S


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = JetsonSettings('/test/control', '/test/status')
        self.tracker = RuntimeTracker('test_robot', self.settings)
        self.sample = RuntimeSample('test_robot', 'boot_a', 1, 10_000_000_000, 'arbitrary_mode',
            False, False, False, False, False, 'UNKNOWN', True, 'DEVICE_ERROR',
            state='ERROR', phase='WAIT', error_message='원문 오류')

    def test_legacy_does_not_construct_ros_extension(self) -> None:
        self.assertIsNone(create_jetson_connection(S(config={}), None))

    def test_invalid_config(self) -> None:
        config = dict(enabled=True, control_state_topic='/test/control', runtime_status_topic='/test/status')
        for change in (dict(control_state_rate_hz=0), dict(unrecognized=True), dict(enabled='true')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                JetsonSettings.from_config(dict(config, **change))

    def test_all_status_values_are_retained_without_readiness_gate(self) -> None:
        self.assertTrue(self.tracker.receive(self.sample, 0))
        state = self.tracker.snapshot(.1)
        self.assertFalse(state['stale'])
        self.assertEqual(state['status']['error_message'], '원문 오류')
        self.assertEqual(state['status']['mode'], 'arbitrary_mode')
        self.assertFalse(state['status']['ready'])
        self.assertTrue(state['status']['recovery_required'])

    def test_wrong_robot_does_not_refresh_and_expiry_recovers(self) -> None:
        self.assertTrue(self.tracker.snapshot(0)['stale'])
        self.tracker.receive(self.sample, 0)
        self.assertFalse(self.tracker.receive(replace(self.sample, robot_id='other'), 2))
        self.assertTrue(self.tracker.snapshot(3)['stale'])
        self.tracker.receive(replace(self.sample, sequence=2), 3)
        self.assertFalse(self.tracker.snapshot(3)['stale'])

    def test_restart_and_clock_changes_are_recorded_without_latch(self) -> None:
        self.tracker.receive(self.sample, 0)
        changed = replace(self.sample, boot_id='boot_b', sequence=0, stamp_ns=1)
        self.tracker.receive(changed, .1)
        self.assertEqual(self.tracker.snapshot(.1)['status']['boot_id'], 'boot_b')
        self.assertFalse(self.tracker.snapshot(.1)['stale'])

    def test_reply_minimum_mode_ready_ttl_without_box_or_pose_gate(self) -> None:
        sample = replace(self.sample, mode='depth_v11', ready=True)
        self.tracker.receive(sample, 0)
        self.assertTrue(self.tracker.ready_to_send(10_000_000_000, 0))
        self.assertFalse(self.tracker.ready_to_send(12_500_000_001, 0))
        self.assertFalse(self.tracker.ready_to_send(10_000_000_000, 2.501))
        self.tracker.receive(replace(sample, sequence=2, mode='other'), .1)
        self.assertFalse(self.tracker.ready_to_send(10_000_000_000, .1))
        self.tracker.receive(replace(sample, sequence=3, ready=False), .2)
        self.assertFalse(self.tracker.ready_to_send(10_000_000_000, .2))

    def test_duplicate_sequence_and_old_boot_do_not_refresh(self) -> None:
        self.tracker.receive(self.sample, 0)
        self.assertFalse(self.tracker.receive(self.sample, 2))
        self.assertTrue(self.tracker.snapshot(2.501)['stale'])
        self.assertTrue(self.tracker.receive(replace(self.sample, boot_id='new', sequence=0), 3))
        self.assertFalse(self.tracker.receive(replace(self.sample, sequence=99), 4))
        self.assertEqual(self.tracker.snapshot(4)['status']['boot_id'], 'new')
        self.assertFalse(self.tracker.receive(replace(self.sample, boot_id=''), 4))


class ControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = ControlTracker(odom_age_s=.5, settle_s=.2, linear_mps=.005,
            angular_rps=.02, future_s=.05)

    def sample(self, offset: float, vx: float = 0., valid: bool = True) -> None:
        stamp = 10_000_000_000 + round(offset*1e9)
        self.tracker.odom(stamp, vx, 0., 0., stamp, offset, valid)

    def values(self, offset: float, **kwargs: bool) -> tuple[int, bool]:
        return self.tracker.values(10_000_000_000+round(offset*1e9), offset,
                                  **dict(motion_idle=True, **kwargs))

    def test_measured_stop_without_estop(self) -> None:
        self.sample(0); self.sample(.2)
        self.assertEqual(self.values(.2), (10_200_000_000, True))

    def test_observation_freshness_boundary_and_recovery(self) -> None:
        self.assertFalse(self.tracker.observation_fresh(10_000_000_000, 0))
        self.sample(0)
        self.assertTrue(self.tracker.observation_fresh(10_200_000_000, .2))
        self.assertFalse(self.tracker.observation_fresh(10_200_000_001, .200000001))
        self.assertFalse(self.tracker.observation_fresh(10_100_000_000, .201))
        self.assertFalse(self.tracker.observation_fresh(10_201_000_000, .1))
        self.sample(.3)
        self.assertTrue(self.tracker.observation_fresh(10_300_000_000, .3))

    def test_stationary_duration_and_original_stamp(self) -> None:
        self.sample(0)
        self.assertFalse(self.values(0)[1])
        self.sample(.2)
        self.assertEqual(self.values(.2), (10_200_000_000, True))

    def test_same_stamp_cannot_accumulate_or_refresh(self) -> None:
        self.sample(0)
        self.tracker.odom(10_000_000_000, 0, 0, 0, 10_400_000_000, .4, True)
        self.assertFalse(self.values(.4)[1])
        self.assertEqual(self.tracker._received_s, 0)

    def test_motion_and_nan_and_frame_reset_evidence(self) -> None:
        self.sample(0); self.sample(.2)
        self.assertTrue(self.values(.2)[1])
        self.sample(.3, .01)
        self.assertFalse(self.values(.3)[1])
        self.sample(.4); self.sample(.5, float('nan'))
        self.assertFalse(self.values(.5)[1])
        self.sample(.6); self.sample(.7, valid=False)
        self.assertFalse(self.values(.7)[1])

    def test_stale_sources_and_navigation_goal_block_stop(self) -> None:
        self.sample(0); self.sample(.2)
        self.assertFalse(self.tracker.values(10_200_000_000, .2, motion_idle=False)[1])
        self.assertFalse(self.values(.71)[1])

    def test_future_and_backward_clock_not_safe(self) -> None:
        self.tracker.odom(10_051_000_000, 0, 0, 0, 10_000_000_000, 0, True)
        self.assertFalse(self.values(0)[1])
        self.sample(0); self.sample(.2); self.values(.2)
        self.assertFalse(self.values(.1)[1])

    def test_gap_restarts_settle_window(self) -> None:
        self.sample(0); self.sample(.6)
        self.assertFalse(self.values(.6)[1])


if __name__ == '__main__':
    unittest.main()
