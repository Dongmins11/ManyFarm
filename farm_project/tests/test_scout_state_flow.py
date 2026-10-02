"""실제 상태 흐름을 검증하되 로봇·영상 장치 I/O는 대체합니다."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'tests'))
from test_scout_segments import SegmentTests, bed, K, C, PRE
sys.path.insert(0, str(PROJECT / 'robot/ros_ws/src/scout_robot'))
sys.path.insert(0, str(PROJECT / 'robot/ros_ws/src/farm_navigation'))

from scout_new.runtime import MissionCanceled
from scout_new.scout_mission import ScoutMission
from scout_new.scout_state_controller import ScoutStateController
from scout_new.scout_communication import ScoutCommunication
from scout_new.states.mission_state import MissionState
import scout_new.scout_mission as mission_module


class StateFlowTests(SegmentTests):
    def run_mission(self, finish='last_segment', failure_at=None, cancel=False,
                    two_beds=False, detections=None, tail_failure=False,
                    late_move=False, cleanup_failure=False, callback=None, patrol=False):
        events, moves, feedback, terminal, captures = [], [], [], [], []
        arrived = threading.Event()
        release = threading.Event()
        node = NS(
            _cfg=dict(vision_config='unused.json', output_dir='runs/scout_survey', base_frame='scout_01/base_footprint',
                      association_distance_m=.065, association_band_half_depth_m=.2, overlap_fraction=.15),
            _vcfg={'preprocess': PRE}, _beds={'BED_01': bed(finish=finish)},
            _python=Path(sys.executable), _shutdown_requested=False,
            _active_goal=None, _navigation_log=[], _motion_uncertain=False,
        )
        if two_beds:
            node._beds['BED_02'] = bed(finish=finish)
        if patrol:
            b = node._beds['BED_01']
            b.cfg['patrol_segments'] = [dict(segment_id=f'SEG_{i:02d}', observation_node_id=n) for i,n in enumerate((4,6,8),1)]
            node._route_graph = NS(nodes={n:b.world(i,0)[:2] for i,n in enumerate((4,6,8),1)})
        node.get_parameter = lambda name: NS(value=False if name == 'headless' else '0')
        node.get_logger = lambda: NS(info=lambda message: events.append(message), error=lambda message: events.append(message))
        node.lookup = lambda *_: np.eye(4)
        node.show = lambda _: None
        request = NS(robot_id='scout_01', task_id='test', section_ids=list(node._beds),
                     map_id='farm_map_v1', frame_id='map', crop_type='PAPRIKA', target_ripeness='RIPE')
        goal = NS(request=request, is_cancel_requested=False, publish_feedback=feedback.append)
        mission = ScoutMission(node)
        controller = ScoutStateController(mission)
        node._state_controller = controller

        def check():
            if controller.stop_requested or goal.is_cancel_requested or node._shutdown_requested:
                raise MissionCanceled('test cancellation')

        node.check = check

        def navigate(xy, yaw):
            # 실제 Navigator의 XY 계약을 검사합니다. XYZ를 허용하면
            # 실물 두 번째 촬영점과 시뮬 bed.world() 이동 오류를 놓칩니다.
            self.assertEqual(len(xy), 2)
            self.assertTrue(np.isfinite([*xy, yaw]).all())
            moves.append(list(xy))
            if late_move and len(moves) == 1:
                arrived.set()
                if not release.wait(5):
                    raise RuntimeError('release timeout')
            if tail_failure and len(moves) == 7:
                self.assertEqual(len(feedback), 5)
                raise RuntimeError('test tail navigation failure')
            return NS(stamp_ns=100)

        def cancel_nav():
            events.append('cancel_confirmed')

        node._navigator = NS(navigate=navigate, stationary_now=lambda: True,
                             preflight_navigation=lambda: {"status":"OK"}, cancel_nav=cancel_nav)
        node._communication = ScoutCommunication.__new__(ScoutCommunication)
        node._communication._node = node

        class FakeObserver:
            def __init__(self, *_):
                pass

            def receive(self, *_):
                return {'ready': True}

            def call(self, op, check, **kwargs):
                check()
                meta = {'session': 'camera', 'pose_frame': 'scout_01/odom', 'stamp_ns': 200 + len(captures),
                        'K': K.tolist(), 'T_odom_camera_optical': C.tolist()}
                if op == 'info':
                    return {'metadata': meta, 'width': 640, 'height': 384}
                if op == 'capture':
                    captures.append(True)
                    if failure_at == len(captures):
                        if cancel:
                            goal.is_cancel_requested = True
                            raise MissionCanceled('test cancellation')
                        raise RuntimeError('test capture failure')
                    points = [(2., 1.14, .8)] if detections is None else detections
                    return {'metadata': meta, 'timings': {}, 'rejected': [],
                            'detections': [dict(position_odom_m=node._beds['BED_01'].world(*point),
                                                class_name='Red', confidence=.9,
                                                mask_box_original_xyxy=[10, 10, 20, 20]) for point in points]}
                if op == 'annotate':
                    return {'saved': kwargs['directory']}
                raise AssertionError(op)

            def close(self):
                events.append('observer_closed')
                if cleanup_failure:
                    raise RuntimeError('test close failure')

        with tempfile.TemporaryDirectory() as tmp, patch.object(mission_module, 'SurveyObserver', FakeObserver):
            node._root = Path(tmp)
            future = controller.start(goal)
            deadline = time.monotonic() + 10
            stop_injected = False
            try:
                while not future.done() and time.monotonic() < deadline:
                    controller.update()
                    if late_move and arrived.is_set() and not stop_injected:
                        # 실제 동작 종료 전에는 결과도 IDLE도 나와서는 안 됩니다.
                        goal.is_cancel_requested = True
                        controller.update()
                        self.assertFalse(future.done())
                        self.assertEqual(controller.state_name, 'NAVIGATION_MOVE')
                        release.set()
                        stop_injected = True
                    if callback is not None:
                        callback(controller, node, mission, goal)
                    time.sleep(.001)
                self.assertTrue(future.done(), events)
                result = future.result()
                terminal.append('success' if result.result_code == 'SUCCESS' else 'canceled' if result.result_code == 'CANCELED' else 'abort')
                self.assertEqual(controller.state_name, 'IDLE')
                paths = list(node._root.glob('runs/scout_survey/*/survey.json'))
                self.assertEqual(len(paths), 1)
                report = json.loads(paths[0].read_text())
                if late_move:
                    self.assertEqual(captures, [])
                    self.assertEqual(len(moves), 1)
                    self.assertLess(events.index('cancel_confirmed'), events.index('observer_closed'))
                if cleanup_failure:
                    self.assertTrue(node._motion_uncertain)
                self.last_events = events
            finally:
                release.set()
                controller.close()
        return result, report, feedback, moves, terminal

    def test_patrol_three_captures_then_idle_without_return(self):
        result, report, _, moves, _ = self.run_mission(patrol=True, detections=[])
        self.assertEqual(result.result_code, 'SUCCESS')
        self.assertEqual(result.completed_segment_count, 3)
        self.assertEqual(len(moves), 3)
        b = bed()
        for actual, offset in zip(moves, (1,2,3)):
            np.testing.assert_allclose(actual[:2], b.world(offset,0)[:2])
        design=report['sections']['BED_01']['design']
        self.assertEqual([s['segment_id'] for s in design['segments']], ['SEG_01','SEG_02','SEG_03'])
        self.assertEqual(design['completion_behavior'], 'WAIT_FOR_COMMAND')

    def test_late_arrival_after_cancel_cannot_start_observation(self):
        result, _, feedback, _, _ = self.run_mission(late_move=True)
        self.assertEqual(result.result_code, 'CANCELED')
        self.assertEqual(feedback, [])

    def test_cleanup_failure_is_not_success(self):
        result, _, _, _, _ = self.run_mission(cleanup_failure=True)
        self.assertEqual(result.result_code, 'FAILED')

    def test_domain_states_own_enter_and_exit(self):
        events = []
        enter, exit = MissionState.enter, MissionState.exit

        def record_enter(state):
            events.append(('enter', state.name))
            enter(state)

        def record_exit(state):
            events.append(('exit', state.name))
            exit(state)

        with patch.object(MissionState, 'enter', record_enter), patch.object(MissionState, 'exit', record_exit):
            self.run_mission()
        self.assertIn(('enter', 'SEGMENT_PROGRESS'), events)
        self.assertIn(('enter', 'SEGMENT_COMPLETE'), events)
        self.assertIn(('enter', 'SECTION_COMPLETE'), events)
        self.assertEqual(events[-1], ('enter', 'IDLE'))
        for previous, current in zip(events, events[1:]):
            self.assertNotEqual(previous[0], current[0])


if __name__ == '__main__':
    # Run the new controller against inherited contracts, not the legacy test class itself.
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StateFlowTests)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
