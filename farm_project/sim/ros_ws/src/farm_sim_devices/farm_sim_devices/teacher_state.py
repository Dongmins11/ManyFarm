"""농장 sample을 원본 Teacher의 상태·82차원 관측으로 연결합니다.

모든 공간 입력은 장착 시 고정한 legacy policy frame, quaternion은 wxyz입니다.
World, Isaac, ROS를 호출하지 않습니다. 원본 계산은 _teacher_vendor/에
보존하며 과실별 reset은 이 객체만 새로 만듭니다. 다른 과실은 관측에 주입하지 않습니다.
"""
from __future__ import annotations

from dataclasses import fields
import math
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
import torch

from ._teacher_vendor.teacher_friction_progress_env import TeacherFrictionProgressEnv
from ._teacher_vendor.settings import TaskSettings
from ._teacher_vendor.quaternion import quat_apply, quat_conjugate
from ._teacher_vendor.logic import (bilateral_contact, qualified_grasp, valid_pull,
                                   captured_break_candidate, mesh_settled_in_box)


CONTROL_DT = 0.05
JOINT_NAMES = ('arm_2_shoulder_pan', 'arm_2_shoulder_lift', 'arm_2_elbow_flex',
               'arm_2_wrist_flex', 'arm_2_wrist_roll', 'arm_2_gripper')
SOURCE_LOWER = (-1.91986, -1.74533, -1.69, -1.65806, -2.74385, -0.174533)
SOURCE_UPPER = (1.91986, 1.74533, 1.69, 1.65806, 2.84121, 1.74533)
SOURCE_HOME = (0., -1.39, .77, .62, .04879632679489654, 1.1)


def finite_array(value: Any, shape: tuple[int, ...], name: str) -> np.ndarray:
    """명시적인 shape와 유한 SI 값을 검사합니다."""
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f'Teacher sample {name}: expected finite {shape}')
    return result


def finite_scalar(value: Any, name: str) -> float:
    """bool을 숫자로 받아들이지 않습니다."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f'Teacher sample {name}: finite number required')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'Teacher sample {name}: nonfinite')
    return result


class TeacherState(TeacherFrictionProgressEnv):
    """한 과실의 상태만 소유하는 원본 Teacher 계산 어댑터입니다."""

    def __init__(self, runtime: Mapping, joint_limits: Mapping, sample: Mapping,
                 *, device: str = 'cpu', deployment: Mapping, kinematics_path: Any,
                 grasp_policy: Any, transport_policy: Any) -> None:
        from ._teacher_vendor.friction_followup import FollowupSpec
        from ._teacher_vendor.pressure_compare import PressureSpec
        from ._teacher_vendor.bridge_pull_risk import RiskPullSpec
        self.kinematics_path = kinematics_path
        super().__init__(runtime, joint_limits, sample, device=device,
            domain=deployment['domain'], domain_split='test', progress_budget=True,
            followup_spec=FollowupSpec(.15, 6., 'baseline'), floor_mode='unified',
            posture_mode='position', stability_mode='pause', pressure_spec=PressureSpec(0.),
            transport_speed_m_s=.035, orientation_length_m=.02, opening_rate_rad_s=.3,
            deposit_timeout_s=6., hold_stiffness_Nm_rad=1., gain_ramp_s=1.,
            path_spec=RiskPullSpec(axial=True, hold_after_detach=True),
            grasp_policy=grasp_policy, transport_policy=transport_policy)

    def _initialize_sample(self, runtime: Mapping, joint_limits: Mapping, sample: Mapping,
                           *, device: str = 'cpu', **kwargs: Any) -> None:
        accepted = {field.name for field in fields(TaskSettings)}
        unknown = set(runtime) - accepted
        if unknown:
            raise ValueError(f'Unknown Teacher runtime settings: {sorted(unknown)}')
        self.settings = TaskSettings(**dict(runtime))
        if (self.settings.task != 'grasp' or self.settings.target_mode != 'nearest'
                or self.settings.sequence or self.settings.attachment_version != 4
                or self.settings.stem_response_version != 6):
            raise ValueError('60Hz 전달본 grasp/nearest, attachment4/response6 계약이 필요합니다.')
        # 원본 selected_teacher_observation와 동일하게 목표 한 슬롯만 표현합니다.
        self.settings.num_fruits = 1
        self.settings.validate()
        if not math.isclose(self.settings.physics_dt * self.settings.decimation, CONTROL_DT,
                            rel_tol=0., abs_tol=1e-12):
            raise ValueError('Teacher control period must remain 0.05 s')
        self.device, self.num_envs = torch.device(device), 1
        self.step_dt = CONTROL_DT
        self.max_episode_length = math.ceil(self.settings.episode_s / self.step_dt)
        self.lower = self._tensor(finite_array(joint_limits['lower'], (6,), 'lower'))
        self.upper = self._tensor(finite_array(joint_limits['upper'], (6,), 'upper'))
        self.home = self._tensor(finite_array(joint_limits.get('home', SOURCE_HOME), (6,), 'home'))
        if not (np.allclose(self.lower.cpu(), SOURCE_LOWER, atol=1e-5, rtol=0.)
                and np.allclose(self.upper.cpu(), SOURCE_UPPER, atol=1e-5, rtol=0.)):
            raise ValueError('관절 제한이 원본 Teacher 정규화 계약과 다릅니다.')
        self.scene = SimpleNamespace(env_origins=self._tensor([[0., 0., 0.]]))
        self.jids = list(range(6))
        self.robot = MeasuredDrive(self.device)
        self.fruits = [SimpleNamespace(data=SimpleNamespace())]
        self.fixed_contact = SimpleNamespace(data=SimpleNamespace())
        self.moving_contact = SimpleNamespace(data=SimpleNamespace())
        self.arm_contact = SimpleNamespace(data=SimpleNamespace())
        self.fruit_colors = ['Red']
        self.visual_updates = False
        self.assignment_status = 'RUNNING'
        self.episode_length_buf = torch.zeros(1, device=self.device, dtype=torch.long)
        self.episode_metrics = {'fruits_collected': 0}
        self._initialize_task_arrays()
        self.other_detached = False
        self.physical_place_time = 0.
        self.physical_success = False
        self.physical_in_box = False
        self._last_sample_time = None
        self._last_detach_time: float | None = None
        self._sample_events: list[dict] = []
        self._has_action = False
        self.fruit_collision_hulls = [self._tensor(self._vertices(sample['collision_vertices']))]
        tip = sample.get('attachment_local', [.017529832318793216, .012588152566927921, .0375])
        self.fruit_tips = self._tensor(finite_array(tip, (3,), 'attachment_local')[None])
        self.accept_sample(sample)
        self.targets = self.robot.data.joint_pos.clone()

    def _tensor(self, value: Any) -> torch.Tensor:
        return torch.as_tensor(value, dtype=torch.float32, device=self.device)

    @staticmethod
    def _vertices(value: Any) -> np.ndarray:
        vertices = np.asarray(value, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < 4 or not np.isfinite(vertices).all():
            raise ValueError('collision_vertices must contain finite target-local 3D collider points')
        return vertices.copy()

    def _initialize_task_arrays(self) -> None:
        """원본 HarvestEnv의 한 목표 버퍼를 초기화합니다. 물리 상태는 쓰지 않습니다."""
        scalar_names = ('grip_time', 'place_time', 'loaded_time', 'detached_time', 'slip',
            'pull_start_x', 'pull_best_retreat', 'pull_recovery_potential', 'stop_time',
            'stop_best_time', 'release_intent_age', 'place_best_time', 'transport_origin',
            'transport_potential', 'pending_detach_time', 'pending_detach_age', 'pending_detach_lost',
            'previous_distance', 'previous_gripper_q')
        bool_names = ('entry_inside', 'release_armed', 'release_intent', 'valid_release', 'bad_release',
            'release_paid', 'has_grasped', 'squeeze_active', 'valid_detach', 'transport_started',
            'pending_detach', 'pending_detach_rejected', 'has_retained', 'grip', 'raw_grip',
            'success', 'failure', 'detach_event', 'grasp_event', 'arm_collision', 'collection_event',
            'pending_next', 'transport_replay', 'easy_episode', 'release_target_unloaded',
            'transport_preload_latched')
        for name in scalar_names:
            setattr(self, name, torch.zeros(1, device=self.device))
        for name in bool_names:
            setattr(self, name, torch.zeros(1, device=self.device, dtype=torch.bool))
        for name in ('grasp_relative', 'release_intent_tcp', 'pending_detach_relative'):
            setattr(self, name, torch.zeros(1, 3, device=self.device))
        self.release_intent_arm = torch.zeros(1, 5, device=self.device)
        self.actions = torch.zeros(1, 6, device=self.device)
        self.previous_actions = self.actions.clone()
        self.break_evidence = torch.zeros(1, 6, device=self.device)
        self.anchors = torch.zeros(1, 1, 3, device=self.device)
        self.attached = torch.ones(1, 1, dtype=torch.bool, device=self.device)
        self.collected = torch.zeros_like(self.attached)
        self.ripe = torch.ones_like(self.attached)
        self.color_ids = torch.zeros(1, 1, dtype=torch.long, device=self.device)
        self.target_index = torch.zeros(1, dtype=torch.long, device=self.device)
        self.target_start_step = torch.zeros_like(self.target_index)
        for name in ('break_timer', 'break_duration', 'break_load', 'load'):
            setattr(self, name, torch.zeros(1, 1, device=self.device))
        self.break_displacement = torch.zeros(1, 1, 3, device=self.device)
        self.applied_stem_force = torch.zeros_like(self.break_displacement)
        self.applied_stem_torque = torch.zeros_like(self.break_displacement)
        self.threshold = torch.full((1, 1), self.settings.break_force, device=self.device)
        self.place_best_distance = torch.full((1,), float('inf'), device=self.device)
        self.transport_preload_origin = torch.zeros(1, device=self.device)
        self.diagnostic_counts: dict = {}
        self.diagnostic_steps = 0
        self.last_diagnostics: dict = {}

    def _t(self, value: torch.Tensor) -> torch.Tensor:
        return value[:, 0]

    def _target_fruit(self) -> SimpleNamespace:
        return self.fruits[0]

    def _tcp(self) -> tuple[torch.Tensor, torch.Tensor]:
        return self.tcp_position, self.tcp_quaternion

    def _target_contact(self, sensor: SimpleNamespace) -> torch.Tensor:
        return sensor.data.force_matrix_w[:, 0, 0]

    def _advance_target(self) -> None:
        """과실 순서는 농장 coordinator가 관리합니다."""

    def _consume_joint_breaks(self) -> None:
        """물리 분리는 device의 시점별 detach_events에서만 받습니다."""

    def accept_sample(self, sample: Mapping) -> float:
        """측정값을 교체하고 물리적 박스 안착을 관찰합니다. 반환값은 경과 시뮬 초입니다."""
        time_s = finite_scalar(sample['time_s'], 'time_s')
        if self._last_sample_time is not None and time_s < self._last_sample_time - 1e-9:
            raise ValueError('Teacher sample time moved backwards')
        dt = 0. if self._last_sample_time is None else max(0., time_s - self._last_sample_time)
        values = {}
        for name in ('q', 'qd'):
            values[name] = self._tensor(finite_array(sample[name], (6,), name)[None])
        for name in ('tcp_position', 'fruit_position', 'fruit_com_position', 'fruit_linear_velocity',
                     'fruit_angular_velocity', 'fixed_force', 'moving_force', 'fixed_net_force',
                     'moving_net_force', 'anchor'):
            values[name] = self._tensor(finite_array(sample[name], (3,), name)[None])
        for name in ('tcp_quaternion', 'fruit_quaternion'):
            raw = finite_array(sample[name], (4,), name)
            if not math.isclose(float(np.linalg.norm(raw)), 1., rel_tol=0., abs_tol=1e-4):
                raise ValueError(f'{name} must be a unit wxyz quaternion')
            values[name] = self._tensor(raw[None])
        arm = np.asarray(sample['arm_forces'], dtype=float)
        if arm.ndim != 2 or arm.shape[1] != 3 or not len(arm) or not np.isfinite(arm).all():
            raise ValueError('arm_forces must be finite (N,3)')
        for name in ('attached', 'other_detached'):
            value = sample.get(name, False)
            if not isinstance(value, (bool, np.bool_)):
                raise ValueError(f'{name} must be bool')
        scalars = {name: finite_scalar(sample[name], name) for name in
                   ('load_N', 'break_timer_s', 'break_threshold_N')}
        if scalars['break_threshold_N'] <= 0 or scalars['break_timer_s'] < 0:
            raise ValueError('invalid stem threshold/timer')
        events = sample.get('detach_events', [])
        if not isinstance(events, list) or any(not isinstance(event, Mapping) for event in events):
            raise ValueError('detach_events must be a list of physical event samples')
        self.robot.data.joint_pos, self.robot.data.joint_vel = values['q'], values['qd']
        self.tcp_position, self.tcp_quaternion = values['tcp_position'], values['tcp_quaternion']
        data = self.fruits[0].data
        for name, key in (('root_link_pos_w', 'fruit_position'), ('root_link_quat_w', 'fruit_quaternion'),
                          ('root_com_pos_w', 'fruit_com_position'), ('root_com_lin_vel_w', 'fruit_linear_velocity'),
                          ('root_com_ang_vel_w', 'fruit_angular_velocity')):
            setattr(data, name, values[key])
        for sensor, prefix in ((self.fixed_contact, 'fixed'), (self.moving_contact, 'moving')):
            sensor.data.force_matrix_w = values[prefix + '_force'][:, None, None]
            sensor.data.net_forces_w = values[prefix + '_net_force'][:, None]
        self.arm_contact.data.net_forces_w = self._tensor(arm[None])
        self.attached[:] = bool(sample['attached'])
        self.anchors[:, 0] = values['anchor']
        self.load[:] = scalars['load_N']
        self.break_timer[:] = scalars['break_timer_s']
        self.threshold[:] = scalars['break_threshold_N']
        self.other_detached = bool(sample.get('other_detached', False))
        self._sample_events = list(events)
        self._last_sample_time = time_s
        self._update_physical_placement(dt)
        return dt

    def _update_physical_placement(self, dt: float) -> None:
        """사용자 물리 성공과 Teacher의 유효 분리·보유 성공을 별도 기록합니다."""
        fruit = self.fruits[0].data
        self.physical_in_box = bool(mesh_settled_in_box(fruit.root_link_pos_w,
            fruit.root_link_quat_w, fruit.root_com_lin_vel_w,
            self.fruit_collision_hulls[0], self.settings)[0])
        # 양측 파지가 아니어도 한 손가락이 과실을 받치면 아직 놓은 것이 아닙니다.
        # 원본 strict 성공 수식은 그대로 두고 사용자 물리 성과에만 적용합니다.
        no_hand_contact = all(bool((self._target_contact(sensor).norm(dim=-1)
                                    < self.settings.contact_threshold)[0])
                              for sensor in (self.fixed_contact, self.moving_contact))
        released = no_hand_contact and not bool(self.attached[0, 0])
        valid = (self.physical_in_box and released and bool(self.valid_detach[0])
                 and bool(self.has_retained[0]) and bool(getattr(self, 'deposit_active', [False])[0])
                 and not bool(self.failure[0]))
        self.physical_place_time = self.physical_place_time + dt if valid else 0.
        self.physical_success = self.physical_place_time + 1e-9 >= self.settings.place_hold_s

    def _consume_detach_evidence(self) -> None:
        """원본 _apply_action의 물리 분리 순간 증거를 재현합니다."""
        for event in self._sample_events:
            event_time = finite_scalar(event['time_s'], 'detach event time_s')
            if event_time > self._last_sample_time + 1e-7:
                raise ValueError('detach event is from the future')
            if self._last_detach_time is not None:
                raise ValueError('동일 목표의 물리 분리 사건은 한 번만 받을 수 있습니다.')
            vectors = {key: self._tensor(finite_array(event[key], (3,), key)[None]) for key in
                       ('fruit_position', 'tcp_position', 'fixed_force', 'moving_force', 'tip_displacement')}
            quaternions = {}
            for key in ('fruit_quaternion', 'tcp_quaternion'):
                value = finite_array(event[key], (4,), key)
                if not math.isclose(float(np.linalg.norm(value)), 1., rel_tol=0., abs_tol=1e-4):
                    raise ValueError('detach quaternion must be unit wxyz')
                quaternions[key] = self._tensor(value[None])
            center = vectors['fruit_position'] + quat_apply(quaternions['fruit_quaternion'],
                self._tensor([[0., 0., -self.settings.length * .08]]))
            distance = (center - vectors['tcp_position']).norm(dim=-1)
            instant = qualified_grasp(bilateral_contact(vectors['fixed_force'], vectors['moving_force'],
                distance, self.settings), distance, self.settings)
            pulling = valid_pull(vectors['tip_displacement'], self.settings)
            self.break_evidence = torch.stack((self.has_grasped.float(), instant.float(), pulling.float(),
                distance, vectors['fixed_force'].norm(dim=-1), vectors['moving_force'].norm(dim=-1)), dim=-1)
            self.break_displacement[:, 0] = vectors['tip_displacement']
            # 원본 _apply_action처럼 분리 순간 값을 보존합니다. 이후20Hz sample의
            # load는 이미0이며, 인장 없이 총변위로 분리된 event의0도 유효한 값입니다.
            self.break_duration[:, 0] = finite_scalar(event.get('break_timer_s', float(self.break_timer[0, 0])),
                                                      'detach break_timer_s')
            self.break_load[:, 0] = finite_scalar(event.get('load_N', float(self.load[0, 0])), 'detach load_N')
            self.detach_event |= self.has_grasped & instant & pulling
            self.valid_detach |= self.detach_event
            if self.settings.spring_grasp_grace:
                candidate = captured_break_candidate(torch.ones_like(self.valid_detach),
                    self.valid_detach, instant, self.has_grasped, self.settings.captured_break_grace)
                self.pending_detach |= candidate
                self.pending_detach_time[candidate] = 0
                self.pending_detach_age[candidate] = 0
                relative = quat_apply(quat_conjugate(quaternions['tcp_quaternion']),
                                      center - vectors['tcp_position'])
                self.pending_detach_relative[candidate] = relative[candidate]
            self._last_detach_time = event_time
        self._sample_events = []

    def finish_control_interval(self) -> None:
        """직전20Hz 명령 이후 측정값으로 원본 상태 전이를 계산합니다."""
        self.episode_length_buf += 1
        self._consume_detach_evidence()
        _, timed_out = self._get_dones()
        if self.other_detached:
            self.failure[:] = True
            self.success[:] = False
            self.last_diagnostics['failure_other_detach'] = torch.ones_like(self.failure)
        if bool(self.failure[0]):
            self.assignment_status = 'FAILED'
        elif bool(self.success[0]):
            self.assignment_status = 'SUCCEEDED'
        elif bool(timed_out[0]):
            self.assignment_status = 'TIMED_OUT'

    def prepare_action(self, action: torch.Tensor) -> None:
        """원본 target 증가량·그리퍼 보정을 적용하며 물리 명령은 보내지 않습니다."""
        if action.shape != (1, 6):
            raise ValueError('Teacher action must have shape (1,6)')
        self._pre_physics_step(action)
        self._has_action = True

    def observation(self) -> dict[str, torch.Tensor]:
        """원본 target-only 82D 관측입니다. 나머지7슬롯은 항상0입니다."""
        return self._get_observations()

    def diagnostics(self) -> dict:
        """정책 성공과 실제 바구니 안착을 분리한 직렬화 가능한 자료입니다."""
        result = {key: value[0].detach().cpu().tolist() if isinstance(value, torch.Tensor) else value
                  for key, value in self.last_diagnostics.items()}
        result.update(physical_in_box=self.physical_in_box,
                      physical_place_hold_s=self.physical_place_time,
                      physical_status='SUCCEEDED' if self.physical_success else 'PENDING',
                      teacher_strict_success=bool(self.success[0]),
                      teacher_status=self.assignment_status)
        result['actuator'] = dict(
            stiffness=self.robot.data.joint_stiffness[0].cpu().tolist(),
            velocity_limits=self.robot.data.joint_vel_limits[0].cpu().tolist())
        for name in ('bridge_hold_time', 'pull_active', 'transport_active', 'deposit_active',
                     'progress_extension', 'progress_3s'):
            result[name] = getattr(self, name)[0].detach().cpu().item()
        return result

    def failure_reason(self) -> str:
        """실제 실패 근거를 표시하고 단순 분리를 성공으로 바꾸지 않습니다."""
        reasons = [key.removeprefix('failure_') for key, value in self.last_diagnostics.items()
                   if key.startswith('failure_') and isinstance(value, torch.Tensor) and bool(value[0])]
        return ','.join(reasons) or ('target_timeout' if self.assignment_status == 'TIMED_OUT' else '')


class MeasuredDrive:
    """전달 제어기의 gain/속도 제한 출력을 보관한다. 실제 적용은 TeacherDevice 책임이다."""

    def __init__(self, device: torch.device) -> None:
        self.data = SimpleNamespace(
            joint_stiffness=torch.tensor([[25.]*5+[8.]], device=device),
            joint_vel_limits=torch.tensor([[1.2]*5+[1.5]], device=device))
        self.actuators = {'gripper': SimpleNamespace(stiffness=self.data.joint_stiffness[:, -1:])}

    def write_joint_stiffness_to_sim(self, values: torch.Tensor, *, joint_ids: list,
                                     env_ids: torch.Tensor) -> None:
        self.data.joint_stiffness[env_ids[:, None], joint_ids] = values

    def write_joint_velocity_limit_to_sim(self, values: torch.Tensor, *, joint_ids: list,
                                          env_ids: torch.Tensor) -> None:
        self.data.joint_vel_limits[env_ids[:, None], joint_ids] = values
