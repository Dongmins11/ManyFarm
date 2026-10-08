"""실제 Teacher 가중치로 선택적 계측의 입력·출력 정확성과 무간섭을 검사한다.

오프라인 CPU 시험이며 Isaac 물리 성공을 검증하지 않는다. 정책의 실제 호출을
관찰하는 hook 이외에 런타임의 추가 추론 또는 정규화 통계 갱신은 없어야 한다.
"""
from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from test_teacher_policy import HAS_RSL
from test_teacher_state import PROJECT, profile, sample

sys.path.insert(0, str(PROJECT / 'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_devices.arm_session import ArmSession
from farm_sim_devices.stem_physics import StemSettings
from farm_sim_runtime.teacher_diagnostics import TeacherRuntimeRecorder

if HAS_RSL:
    import torch
    from farm_sim_devices.teacher_policy import TeacherController


@unittest.skipUnless(HAS_RSL, 'PyTorch/RSL-RL 설치 환경에서 실제 가중치로 검사합니다.')
class TeacherDiagnosticTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            cls.plain = TeacherController(profile(), project_root=PROJECT)
            cls.traced = TeacherController(profile(), project_root=PROJECT)
            cls.traced.enable_diagnostic_trace()
            cls.plain.start_target('initial', sample())
            cls.traced.start_target('initial', sample())

    def setUp(self) -> None:
        self.plain.enable_diagnostic_trace(False)
        self.traced.enable_diagnostic_trace()
        self.plain.start_target('target', sample())
        self.traced.start_target('target', sample())

    def test_default_off_and_repeated_enable_do_not_duplicate_hooks(self) -> None:
        self.assertFalse(self.plain._diagnostic_enabled)
        self.assertEqual(self.plain._diagnostic_hooks, [])
        self.assertNotIn('diagnostic_trace', self.plain.tick(sample()).diagnostics)
        handles = tuple(self.traced._diagnostic_hooks)
        self.assertEqual(len(handles), 8)
        self.traced.enable_diagnostic_trace()
        self.traced.start_target('next', sample())
        self.assertEqual(tuple(self.traced._diagnostic_hooks), handles)
        self.traced.enable_diagnostic_trace(False)
        self.assertEqual(self.traced._diagnostic_hooks, [])
        self.assertNotIn('diagnostic_trace', self.traced.tick(sample()).diagnostics)
        self.traced.enable_diagnostic_trace()
        self.assertEqual(len(self.traced._diagnostic_hooks), 8)
        with self.assertRaises(ValueError):
            self.traced.enable_diagnostic_trace('yes')

    def test_actual_raw_time_adjusted_normalized_inputs_and_actor_output_are_saved(self) -> None:
        controller = self.traced
        controller.policy.stage_steps[:] = 17
        original = controller.state.observation()['policy'][0].clone()
        result = controller.tick(sample())
        trace = result.diagnostics['diagnostic_trace']
        self.assertEqual(trace['source'], 'actual_forward_hooks')
        self.assertTrue(trace['policy_executed'])
        self.assertEqual(trace['selected_expert'], -1)
        self.assertEqual(trace['policy_tick_index'], 1)
        self.assertIsNone(trace['actual_control_dt_s'])
        self.assertEqual(len(trace['observation_raw']), 82)
        self.assertEqual(len(trace['observation_expert']), 82)
        self.assertEqual(len(trace['observation_normalized']), 82)
        covered = [index for _, start, stop in trace['observation_layout'] for index in range(start, stop)]
        self.assertEqual(covered, list(range(82)))
        np.testing.assert_array_equal(trace['observation_raw'], original.numpy())
        adjusted = original.clone()
        adjusted[42] = 1.-17/controller.state.max_episode_length
        np.testing.assert_allclose(trace['observation_expert'], adjusted.numpy(), atol=1e-7)
        self.assertNotEqual(trace['observation_raw'][42], trace['observation_expert'][42])
        expert = controller.policy.grasp_expert
        with torch.no_grad():
            normalized = expert.actor_obs_normalizer(adjusted[None])
            raw = expert.actor(normalized)
        np.testing.assert_array_equal(trace['observation_normalized'], normalized[0].numpy())
        np.testing.assert_array_equal(trace['expert_raw_action'], raw[0].numpy())
        np.testing.assert_array_equal(trace['final_action'], result.diagnostics['action'])
        np.testing.assert_array_equal(trace['joint_targets'], result.joint_targets)
        # JSONL에 그대로 넣을 수 있고 외부 검사의 추가 호출은 이미 반환한 tick을 바꾸지 않는다.
        json.dumps(trace, allow_nan=False)
        self.assertEqual(set(trace['expert_calls']), {'-1', '0', '1', '2'})
        for call in trace['expert_calls'].values():
            self.assertEqual(call['normalizer_calls'], 1)
            self.assertEqual(call['actor_calls'], 1)
            self.assertFalse(call['normalizer_training'])
            self.assertFalse(call['actor_training'])
            np.testing.assert_array_equal(call['normalizer_output'], call['actor_input'])

    def test_opt_in_preserves_actions_targets_and_normalizer_state_over_multiple_ticks(self) -> None:
        experts = [self.traced.policy.grasp_expert, *self.traced.policy.experts]
        before = [{name: value.clone() for name, value in expert.actor_obs_normalizer.state_dict().items()}
                  for expert in experts]
        previous = None
        for tick in range(5):
            plain, traced = self.plain.tick(sample(tick*.05)), self.traced.tick(sample(tick*.05))
            np.testing.assert_array_equal(plain.joint_targets, traced.joint_targets)
            self.assertEqual((plain.status, plain.reason, plain.stage), (traced.status, traced.reason, traced.stage))
            without_trace = {key: value for key, value in traced.diagnostics.items() if key != 'diagnostic_trace'}
            self.assertEqual(plain.diagnostics, without_trace)
            trace = traced.diagnostics['diagnostic_trace']
            self.assertEqual(trace['policy_tick_index'], tick+1)
            if tick:
                self.assertAlmostEqual(trace['actual_control_dt_s'], .05)
                self.assertEqual(previous['time_s'], (tick-1)*.05)
            previous = trace
        for expected, expert in zip(before, experts):
            for name, value in expert.actor_obs_normalizer.state_dict().items():
                torch.testing.assert_close(value, expected[name], rtol=0, atol=0)

    def test_transport_ramp_and_fixed_release_keep_raw_and_executed_actions_distinct(self) -> None:
        controller = self.traced
        controller.policy.grasp_active[:] = False
        controller.policy.stage[:] = 1
        result = controller.tick(sample())
        trace = result.diagnostics['diagnostic_trace']
        self.assertEqual(trace['selected_expert'], 1)
        expected = np.clip(trace['expert_raw_action'], -1., 1.)
        expected[:5] *= .25
        np.testing.assert_allclose(trace['final_action'], expected, atol=1e-7)
        controller.start_target('release', sample(1.))
        controller.policy.grasp_active[:] = False
        controller.policy.stage[:] = 2
        before = controller.state.targets[0].clone()
        result = controller.tick(sample(1.))
        trace = result.diagnostics['diagnostic_trace']
        self.assertEqual(trace['selected_expert'], 2)
        np.testing.assert_allclose(trace['staged_action'], [0., 0., 0., 0., 0., .15], atol=1e-7)
        self.assertFalse(np.allclose(trace['expert_raw_action'], trace['staged_action']))
        np.testing.assert_array_equal(result.joint_targets[:5], before[:5].numpy())
        self.assertAlmostEqual(result.joint_targets[5]-float(before[5]), .009, places=6)

    def test_handoff_records_real_flags_and_observed_stage_change(self) -> None:
        controller = self.traced
        controller.state.has_grasped[:] = True
        controller.state.grip[:] = True
        controller.state.valid_detach[:] = True
        controller.state.has_retained[:] = True
        result = controller.tick(sample())
        trace = result.diagnostics['diagnostic_trace']
        self.assertTrue(trace['state_before']['has_grasped'])
        self.assertTrue(trace['state_before']['grip'])
        self.assertTrue(trace['state_before']['has_retained'])
        self.assertEqual(trace['state_before']['expert_stage'], -1)
        self.assertEqual(trace['state_after']['expert_stage'], 1)
        self.assertTrue(trace['stage_changed'])
        self.assertEqual(trace['stage_transition']['reason_source'], 'derived_from_observed_stage_change')
        self.assertEqual(trace['stage_transition']['reason'], 'expert_-1_to_1')

    def test_existing_arm_session_policy_jsonl_keeps_nested_actual_trace(self) -> None:
        device = SimpleNamespace(command=Mock())
        session = ArmSession('test-session', 'harvester', 'map', device, self.traced,
                             SimpleNamespace(), profile()['session'], PROJECT / 'sim/runs/unused')
        session._target = 'target'
        with io.StringIO() as output:
            session._trace = output
            session._policy_tick(0., sample())
            row = json.loads(output.getvalue())
        self.assertEqual(row['event'], 'POLICY')
        trace = row['diagnostics']['diagnostic_trace']
        self.assertEqual(len(trace['observation_raw']), 82)
        self.assertEqual(len(trace['expert_raw_action']), 6)
        self.assertEqual(trace['joint_targets_semantics'], 'new_policy_target')
        self.assertEqual(row['joint_targets'], trace['joint_targets'])
        device.command.assert_called_once_with(row['joint_targets'])

    def test_cancel_terminal_and_observe_never_relabel_old_inputs_as_new_inference(self) -> None:
        controller = self.traced
        first = controller.tick(sample())
        controller.cancel()
        canceled = controller.tick(sample(.05))
        trace = canceled.diagnostics['diagnostic_trace']
        self.assertFalse(trace['policy_executed'])
        self.assertEqual(trace['expert_calls'], {})
        self.assertNotIn('observation_raw', trace)
        self.assertNotIn('expert_raw_action', trace)
        np.testing.assert_array_equal(first.joint_targets, canceled.joint_targets)
        observed = controller.observe(sample(.1)).diagnostics['diagnostic_trace']
        self.assertEqual(observed['kind'], 'observe')
        self.assertFalse(observed['policy_executed'])
        self.assertEqual(observed['expert_calls'], {})
        self.assertNotIn('joint_targets', observed)
        np.testing.assert_array_equal(observed['held_joint_targets'], first.joint_targets)
        controller.start_target('new-target', sample(1.))
        new = controller.tick(sample(1.)).diagnostics['diagnostic_trace']
        self.assertEqual(new['policy_tick_index'], 1)
        self.assertEqual(new['target_id'], 'new-target')
        self.assertIsNone(new['actual_control_dt_s'])


class TeacherRuntimeRecorderTests(unittest.TestCase):
    """가짜 SDK 측정으로 연속 기록의 gate와 이벤트 비소비를 검사한다."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.world = SimpleNamespace(current_time_step_index=0,
            get_physics_dt=lambda: 1./480., get_rendering_dt=lambda: 1./60.,
            get_physics_context=lambda: SimpleNamespace(get_gravity=lambda: (0., 0., -9.81)),
            stage=SimpleNamespace(Traverse=lambda: []))
        ctl = SimpleNamespace(get_gains=lambda: (np.ones(6)*25., np.ones(6)*1.5),
                              get_max_efforts=lambda: np.array([2., 2., 2., 2., 2., .5]))
        # 팔 물성 readback에 사용하는 초기화된 PhysX view 계약도 제공한다.
        view = SimpleNamespace(body_names=['body'+str(i) for i in range(6)],
            get_body_masses=lambda: np.full((1, 6), .1),
            get_body_inertias=lambda: np.tile(np.eye(3).reshape(1, 1, 9), (1, 6, 1)),
            get_body_coms=lambda: (np.zeros((1, 6, 3)), np.tile([1., 0., 0., 0.], (1, 6, 1))),
            get_dof_limits=lambda: np.tile([-2., 2.], (1, 6, 1)),
            get_joint_max_velocities=lambda: np.full((1, 6), 1.2))
        attachments = SimpleNamespace(settings=StemSettings(), paths=['/fruit'], masses=np.array([.009]),
            local_com=np.zeros((1, 3)), inverse_inertia=np.eye(3)[None], records=[{'color': 'red'}],
            rest_orientation=np.array([[1., 0., 0., 0.]]), axes=np.array([[1., 0., 0.]]),
            tips=np.array([[0., 0., .0375]]), anchors=np.array([[1., 2., 3.]]),
            thresholds=np.array([2.5]), diagnostic_state=Mock(return_value={'attached': True}))
        self.device = SimpleNamespace(world=self.world, attachments=attachments,
            articulation=SimpleNamespace(get_articulation_controller=lambda: ctl,
                _articulation_view=view, dof_names=['j'+str(i) for i in range(6)],
                get_applied_action=lambda: SimpleNamespace(joint_positions=np.arange(6)/20.)),
            _joint_indices=np.arange(6),
            joint_names=['j'+str(i) for i in range(6)], lower=np.full(6, -2.), upper=np.full(6, 2.),
            home=np.zeros(6), _policy_arm=np.zeros(3), _finger_paths=['/fixed', '/moving'], paths=['/fruit'],
            _arm_view=SimpleNamespace(prim_paths=['/arm']), config={'box_min': [0., 0., 0.], 'box_max': [1., 1., 1.]},
            robot_path='/robot', _selected=None, _path_indices={'/fruit': 0},
            _policy_world=np.eye(4), _dock_world_arm=np.eye(4),
            joint_positions=Mock(return_value=np.arange(6)/10.),
            joint_velocities=Mock(return_value=np.zeros(6)),
            arm_world_transform=Mock(return_value=np.eye(4)),
            contacts_for_recovery=Mock(return_value={'max_force_N': .1}),
            _previous={'time_s': 0., 'q': np.arange(6)/10., 'collision_vertices': np.zeros((4, 3))},
            _events=[{'time_s': .01, 'load_N': 2.5}],
            sample=Mock(side_effect=AssertionError('진단은 제어용 이벤트를 소비하면 안 됩니다.')))
        self.arm = ArmSession('test', 'robot', 'map', self.device, Mock(), Mock(),
                              {'control_dt_s': .05}, self.directory)
        robot = {'arm': self.arm, 'arm_device': self.device,
                 'base': SimpleNamespace(pose=lambda: (np.zeros(3), np.array([1., 0., 0., 0.])))}
        with patch.object(TeacherRuntimeRecorder, '_usd_tree', return_value=[]):
            self.recorder = TeacherRuntimeRecorder(robot, self.directory)
        self.addCleanup(self.recorder.close)
        self.recorder._usd_tree = Mock(return_value=[])

    def records(self) -> list[dict]:
        return [json.loads(line) for line in (self.directory / 'continuous.jsonl').read_text().splitlines()]

    def test_idle_gate_records_twenty_hz_and_actual_physics_timing(self) -> None:
        for time_s in (0., 1./60., 2./60., .05, .06, .1):
            self.world.current_time_step_index = round(time_s*480)
            self.recorder.sample(time_s)
        rows = self.records()
        self.assertEqual([row['sim_s'] for row in rows], [0., .05, .1])
        self.assertEqual([row['physics_step'] for row in rows], [0, 24, 48])
        self.assertEqual([row['index'] for row in rows], [0, 1, 2])
        self.assertIsNone(rows[0]['recorded_interval_s'])
        self.assertAlmostEqual(rows[1]['recorded_interval_s'], .05)
        self.assertEqual(rows[-1]['physics_dt_s'], 1./480.)
        np.testing.assert_array_equal(rows[-1]['physx_joint_position_targets_rad'], np.arange(6)/20.)

    def test_running_gate_aligns_with_control_tick_instead_of_render_frame(self) -> None:
        self.recorder.sample(0.)
        self.arm.state['status'] = 'RUNNING'
        self.arm._last_tick = 2./60.
        self.recorder.sample(.05)
        self.assertEqual(len(self.records()), 1)
        self.arm._last_tick = 4./60.
        self.recorder.sample(4./60.)
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(self.records()[-1]['control_tick_sim_s'], 4./60.)

    def test_selected_target_snapshot_does_not_consume_events_or_mutate_buffers(self) -> None:
        self.device._selected = '/fruit'
        events = deepcopy(self.device._events)
        before_sample = deepcopy(self.device._previous)
        before_anchor = self.device.attachments.anchors.copy()
        self.recorder.sample(0.)
        self.recorder.sample(.05)
        self.device.sample.assert_not_called()
        self.assertEqual(self.device._events, events)
        np.testing.assert_array_equal(self.device._previous['q'], before_sample['q'])
        np.testing.assert_array_equal(self.device._previous['collision_vertices'], before_sample['collision_vertices'])
        np.testing.assert_array_equal(self.device.attachments.anchors, before_anchor)
        self.recorder._usd_tree.assert_called_once_with('/fruit')
        self.assertEqual(len(list(self.directory.glob('target_*.json'))), 1)
        row = self.records()[0]
        self.assertNotIn('collision_vertices', row['sample'])
        self.assertEqual(row['fruit_physics'], {'attached': True})

    def test_safe_and_unsafe_terminal_states_keep_recording_after_control_stops(self) -> None:
        self.arm.state['status'] = 'RUNNING'
        self.arm._last_tick = 0.
        self.recorder.sample(0.)
        self.arm.state.update(status='SUCCESS', safe_stopped=True)
        self.recorder.sample(.05)
        self.arm.state.update(status='FAILED', safe_stopped=False)
        self.arm._blocked = True
        self.assertTrue(self.arm.busy)
        self.recorder.sample(.1)
        self.assertEqual([row['state']['status'] for row in self.records()], ['RUNNING', 'SUCCESS', 'FAILED'])


if __name__ == '__main__':
    unittest.main()
