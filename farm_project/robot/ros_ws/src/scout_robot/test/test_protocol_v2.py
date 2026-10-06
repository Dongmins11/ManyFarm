"""Offline behavior checks with slots generated from the supplied ROS definitions.

These tests do not replace the generated ROS-type/CDR check in farm_interfaces.
Run this file directly to keep the ROS doubles isolated from other test suites.
"""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(SRC / 'scout_robot'), str(SRC / 'harvest_robot')]


def module(name, **values):
    value = ModuleType(name)
    value.__dict__.update(values)
    return value


types = {}


def schema(name, text):
    fields = [line.split('#')[0].strip().split() for line in text.splitlines()]
    fields = [line for line in fields if line]
    def init(self, **kwargs):
        for typename, field in fields:
            if typename.endswith('[]'): value = []
            elif typename == 'string': value = ''
            elif typename in ('float64', 'float32'): value = 0.0
            elif typename.startswith(('int', 'uint')): value = 0
            else: value = types[typename]()
            setattr(self, field, kwargs.pop(field, value))
        if kwargs: raise TypeError(kwargs)
    return type(name, (), {'__slots__': [f for _, f in fields], '__init__': init})


types['geometry_msgs/Point'] = schema('Point', 'float64 x\nfloat64 y\nfloat64 z')
for name in ('RobotPose', 'HarvestTask'):
    types['farm_interfaces/' + name] = schema(name, (SRC / 'farm_interfaces/msg' / (name + '.msg')).read_text())
actions = {}
for name in ('ScoutArea', 'HarvestTask'):
    parts = (SRC / 'farm_interfaces/action' / (name + '.action')).read_text().split('---')
    actions[name] = NS(**{kind: schema(name + kind, text) for kind, text in zip(('Goal', 'Result', 'Feedback'), parts)})
sys.modules.update({
    'farm_interfaces': module('farm_interfaces'),
    'farm_interfaces.msg': module('farm_interfaces.msg', HarvestTask=types['farm_interfaces/HarvestTask']),
    'farm_interfaces.action': module('farm_interfaces.action', **actions),
    'rclpy': module('rclpy'),
    'rclpy.action': module('rclpy.action', ActionServer=lambda *a, **k: None,
                           GoalResponse=NS(ACCEPT=1, REJECT=2), CancelResponse=NS(ACCEPT=1, REJECT=2)),
    'rclpy.action.server': module('rclpy.action.server', ServerGoalHandle=object),
    'scout_robot.survey_core': module('scout_robot.survey_core', Survey=object, StraightBed=object),
    'scout_new.observer': module('scout_new.observer', SurveyObserver=object),
})
from scout_robot.task_messages import tasks_from_windows
from scout_new.mission_types import MissionContext
from scout_new.scout_mission import ScoutMission
from scout_new.scout_communication import ScoutCommunication
from scout_new.states.section_complete_state import SectionCompleteState
from scout_new.states.segment_complete_state import SegmentCompleteState
from harvest_robot.contract import validate_task, result_fields


def windows():
    return [dict(window_id=name, segment_id='SEC01_G01', expected_count=count,
                 goal_pose=dict(frame_id='map', position=[-5.95, 8.3, 0.0], yaw=-1.57))
            for name, count in [('session_SEC01_W009', 2), ('WIN_A01_01', 3)]]


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logs = []
        self.node = NS(_navigation_log=[], get_logger=lambda: NS(error=self.logs.append))
        self.mission = ScoutMission(self.node)
        request = actions['ScoutArea'].Goal(robot_id='scout_01', task_id='SCOUT_TEST', section_id='SEC01')
        self.context = MissionContext(goal=NS(request=request), session='test', folder=Path(self.tmp.name),
            report={'sections': {'SEC01': {'survey': {'windows': windows()}}}}, started_wall=time.monotonic())
        self.mission._context = self.context

    def test_result_order_exact_four_field_tasks_and_totals(self):
        self.mission.save_segment()
        result = self.mission.finish('SUCCESS')
        self.assertEqual([t.window_id for t in result.harvest_tasks], ['session_SEC01_W009', 'WIN_A01_01'])
        self.assertEqual((result.section_id, result.harvest_task_count, result.total_expected_count), ('SEC01', 2, 5))
        for task in result.harvest_tasks:
            self.assertEqual(task.__slots__, ['task_id', 'window_id', 'goal_pose', 'expected_count'])
        data = json.loads((self.context.folder / 'survey.json').read_text())
        self.assertEqual(data['harvest_tasks'][0]['goal_pose']['position']['x'], -5.95)

    def test_failed_and_canceled_keep_saved_partial_tasks(self):
        self.mission.save_segment()
        self.context.report['sections']['SEC01']['survey']['windows'] = windows()[:1]
        with patch.object(self.mission, 'save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.mission.save_segment()
        for code in ('FAILED', 'CANCELED'):
            result = self.mission.finish(code, RuntimeError('stopped'))
            self.assertEqual((result.result_code, len(result.harvest_tasks), result.total_expected_count), (code, 2, 5))

    def test_empty_result_and_final_save_failure(self):
        result = self.mission.finish('SUCCESS')
        self.assertEqual((result.harvest_tasks, result.harvest_task_count, result.total_expected_count), ([], 0, 0))
        self.mission.save_segment()
        with patch.object(self.mission, 'save', side_effect=OSError('disk full')):
            result = self.mission.finish('SUCCESS')
        self.assertEqual((result.result_code, result.error_code, len(result.harvest_tasks)), ('FAILED', 'REPORT_SAVE_FAILED', 2))

    def test_harvest_accepts_scout_ids_without_removed_fields(self):
        config = dict(robot_id='harvest_01', map_id='farm_map_v1')
        for task in tasks_from_windows(windows()):
            goal = actions['HarvestTask'].Goal(robot_id='harvest_01', map_id='farm_map_v1', harvest_task=task)
            validate_task(goal, config)
            for code in ('SUCCESS', 'FAILED', 'CANCELED'):
                result = actions['HarvestTask'].Result(**result_fields(goal, code))
                self.assertEqual(result.window_id, task.window_id)
                self.assertEqual((result.harvested_count, result.failed_count), (0, 0))
            task.goal_pose.position.x = float('nan')
            with self.assertRaises(ValueError): validate_task(goal, config)
            task.goal_pose.position.x = -5.95
            task.window_id = ''
            with self.assertRaises(ValueError): validate_task(goal, config)

    def test_section_feedback_empty_and_no_next_section(self):
        emitted, completed = [], []
        communication = ScoutCommunication.__new__(ScoutCommunication)
        self.node._communication = communication
        self.context.goal.publish_feedback = emitted.append
        self.context.design = {'finish_at': 'last_observation', 'segments': [{'segment_id': 'SEC01_G01', 'offset_m': 1.0}]}
        self.context.bed = NS(length=2.0)
        controller = NS(complete=completed.append)
        state = SectionCompleteState(self.mission, controller)
        state._on_section_saved(None)
        self.assertEqual(len(completed), 1)
        f = emitted[0]
        self.assertEqual((f.section_id, f.segment_id, f.segment_expected_count, f.harvest_tasks), ('SEC01', '', 0, []))

    def test_last_segment_has_progress_feedback(self):
        emitted, transitions = [], []
        self.node.show = lambda _: None
        self.node._communication = ScoutCommunication.__new__(ScoutCommunication)
        self.context.goal.publish_feedback = emitted.append
        self.context.survey = object()
        self.context.design = {'segments': [{'segment_id': 'SEC01_G01'}]}
        self.context.completed_segments = 1
        self.context.segment_expected_count = 2
        controller = NS(request_transition=lambda *x: transitions.append(x))
        state = SegmentCompleteState(self.mission, controller)
        state._on_record_saved(None)
        self.assertEqual((emitted[0].phase, emitted[0].segment_id, emitted[0].harvest_tasks), ('SEGMENT_COMPLETE', 'SEC01_G01', []))
        self.assertEqual(len(transitions), 1)


if __name__ == '__main__': unittest.main(verbosity=2)
