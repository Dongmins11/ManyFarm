"""검증한 4개 Teacher 정책의 CPU 추론과 농장 순수 상태 어댑터.

물리 step·관절 순간이동·ROS 호출은 없습니다. root runtime가20Hz에 tick하고
반환한6개 joint target만 device로 보냅니다. 실패 뒤 다음 목표 선택은 coordinator 책임입니다.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import torch

from .teacher_state import TeacherState, CONTROL_DT, JOINT_NAMES, finite_scalar
from ._teacher_vendor.staged_teacher import StagedTeacher


# Python slice의 [start, stop) 순서다. 관측 생성 계산은 원본 kernel에만 둔다.
DIAGNOSTIC_OBSERVATION_LAYOUT = (
    ('joint_position_normalized', 0, 6), ('joint_velocity_div_1_5', 6, 12),
    ('previous_normalized_action', 12, 18), ('tcp_position_policy', 18, 21),
    ('tcp_quaternion_wxyz', 21, 25), ('fruit_root_minus_tcp', 25, 28),
    ('fruit_com_linear_velocity_policy', 28, 31), ('fruit_quaternion_wxyz', 31, 35),
    ('legacy_box_reference_minus_tcp', 35, 38), ('attached', 38, 39),
    ('task_progress', 39, 40), ('has_grasped', 40, 41), ('valid_detach', 41, 42),
    ('remaining_time_fraction', 42, 43), ('placement_hold_fraction', 43, 44),
    ('fruit_relative_xyz_8_slots_target_only', 44, 68), ('fruit_mask_8_slots_target_only', 68, 76),
    ('anchor_minus_tcp', 76, 79), ('load_div_break_force', 79, 80),
    ('break_timer_div_break_hold', 80, 81), ('threshold_div_break_force', 81, 82))


@dataclass(frozen=True)
class TeacherStep:
    """관절 출력과 실제/Teacher 판정을 함께 전달합니다."""
    joint_targets: list[float]
    status: str
    reason: str
    stage: int
    diagnostics: dict


class TeacherController:
    """정책을 한 번 로드하고 과실별 상태만 교체합니다."""

    def __init__(self, profile: Mapping, *, project_root: Path, device: str = 'cpu') -> None:
        from rsl_rl.modules import ActorCritic
        from tensordict import TensorDict

        self.profile = dict(profile)
        self.device = torch.device(device)
        self.project_root = Path(project_root).resolve()
        self.runtime = dict(profile['runtime'])
        self.joint_limits = dict(profile['joint_limits'])
        self.execution = dict(profile['action_execution'])
        if self.execution.get('release_mode') not in ('fixed', 'policy'):
            raise ValueError('Teacher release_mode must be explicit')
        if self.execution.get('transport_recovery', False):
            raise ValueError('이번 농장 경로는 원본9g의 transport_recovery=False만 지원합니다.')
        self.paths = {}
        expected_tasks = {'ENTRY_CKPT': 'grasp', 'PULL_CKPT': 'pull',
                          'TRANSPORT_CKPT': 'transport', 'PLACE_CKPT': 'place'}
        for key, task in expected_tasks.items():
            spec = profile['checkpoints'][key]
            path = (self.project_root / spec['path']).resolve()
            if not path.is_relative_to(self.project_root):
                raise ValueError('정책 경로는 프로젝트 내부여야 합니다.')
            metadata = path.parent / 'run.json'
            for file, digest in ((path, spec['sha256']), (metadata, spec['run_sha256'])):
                if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                    raise ValueError(f'Teacher artifact hash mismatch: {file}')
            if json.loads(metadata.read_text())['task']['task'] != task:
                raise ValueError(f'Teacher stage metadata mismatch: {key}')
            self.paths[key] = path
        example = TensorDict({'policy': torch.zeros(1, 82, device=self.device)}, batch_size=[1])
        self.template = ActorCritic(example, {'policy': ['policy'], 'critic': ['policy']}, 6,
            init_noise_std=.6, actor_obs_normalization=True, critic_obs_normalization=True,
            actor_hidden_dims=[256, 256, 128], critic_hidden_dims=[256, 256, 128], activation='elu').to(self.device)
        state = torch.load(self.paths['PULL_CKPT'], map_location=self.device, weights_only=True)
        self.template.load_state_dict(state['model_state_dict'], strict=True)
        self.template.eval()
        self.state: TeacherState | None = None
        self.policy: StagedTeacher | None = None
        self.target_id: str | None = None
        self._last_control_time: float | None = None
        self._cancelled = False
        self._diagnostic_enabled = False
        self._diagnostic_hooks: list[Any] = []
        self._diagnostic_capture: dict | None = None
        self._diagnostic_trace: dict | None = None
        self._diagnostic_tick = 0

    def enable_diagnostic_trace(self, enabled: bool = True) -> None:
        """선택적 읽기 전용 추론 계측이다. 추가 추론·normalizer 갱신을 하지 않는다.

        실제 policy가 생성된 뒤 forward hook을 설치한다. 활성화 전 TARGET에도
        호출할 수 있으며 다시 호출해도 hook을 중복 등록하지 않는다.
        """
        if type(enabled) is not bool:
            raise ValueError('진단 활성화 값은 bool이어야 합니다.')
        self._diagnostic_enabled = enabled
        if enabled:
            self._install_diagnostic_hooks()
        else:
            for handle in self._diagnostic_hooks:
                handle.remove()
            self._diagnostic_hooks.clear()
            self._diagnostic_capture = self._diagnostic_trace = None

    @staticmethod
    def _diagnostic_value(value: torch.Tensor) -> Any:
        """실제 호출 텐서를 즉시 복사해 이후 in-place 후처리와 분리한다."""
        return value.detach().cpu().clone()[0].tolist()

    def _install_diagnostic_hooks(self) -> None:
        """실제 normalizer와 actor 입출력만 관찰하고 반환값을 바꾸지 않는다."""
        if not self._diagnostic_enabled or self.policy is None or self._diagnostic_hooks:
            return
        experts = [(-1, 'entry_grasp', self.policy.grasp_expert),
                   *[(index, name, expert) for index, (name, expert) in
                     enumerate(zip(('pull', 'transport', 'place'), self.policy.experts))]]

        def hook(stage: int, name: str, role: str) -> Any:
            def capture(module: Any, inputs: tuple, output: torch.Tensor) -> None:
                # 외부 검사에서 전문가를 직접 호출해도 현재 실제 tick만 기록한다.
                if self._diagnostic_capture is None:
                    return
                experts = self._diagnostic_capture['expert_calls']
                record = experts.setdefault(str(stage), dict(stage=stage, name=name))
                record[role+'_input'] = self._diagnostic_value(inputs[0])
                record[role+'_output'] = self._diagnostic_value(output)
                record[role+'_training'] = bool(module.training)
                record[role+'_calls'] = record.get(role+'_calls', 0)+1
            return capture

        for stage, name, expert in experts:
            self._diagnostic_hooks.append(expert.actor_obs_normalizer.register_forward_hook(
                hook(stage, name, 'normalizer')))
            self._diagnostic_hooks.append(expert.actor.register_forward_hook(hook(stage, name, 'actor')))

    def _diagnostic_state(self) -> dict:
        """파지·분리·보유·놓기의 실제 내부 상태를 판정 재계산 없이 복사한다."""
        assert self.state is not None and self.policy is not None
        names = ('expert_stage', 'target_index', 'has_grasped', 'has_retained', 'grip', 'raw_grip',
                 'entry_inside', 'entry_grasp_active', 'valid_detach', 'pending_detach',
                 'pending_detach_rejected', 'release_armed', 'release_intent', 'valid_release',
                 'bad_release', 'success', 'failure', 'arm_collision', 'squeeze_active',
                 'grip_time', 'stop_time', 'place_time', 'detached_time', 'pending_detach_time',
                 'pending_detach_age', 'pending_detach_lost')
        result = {name: self._diagnostic_value(getattr(self.state, name)) for name in names
                  if hasattr(self.state, name)}
        result.update(attached=bool(self.state.attached[0, 0]),
                      policy_color_id=int(self.state.color_ids[0, 0]),
                      assignment_status=self.state.assignment_status,
                      physical_in_box=self.state.physical_in_box,
                      physical_success=self.state.physical_success,
                      routing_stage=int(self.policy.stage[0]),
                      stage_steps=float(self.policy.stage_steps[0]),
                      routing_active=bool(self.policy.active[0]),
                      grasp_active=bool(self.policy.grasp_active[0]))
        return result

    def start_target(self, target_id: str, initial_sample: Mapping) -> None:
        """물리 reset 없이 측정 관절 위치에서 새 과실의 정책 상태를 만듭니다."""
        if not isinstance(target_id, str) or not target_id:
            raise ValueError('persistent target_id is required')
        state = TeacherState(self.runtime, self.joint_limits, initial_sample, device=str(self.device))
        if not bool(state.attached[0, 0]):
            raise ValueError('Teacher target must still be attached at assignment')
        if self.policy is None:
            policy = StagedTeacher(state, self.template, self.paths['TRANSPORT_CKPT'],
                self.paths['PLACE_CKPT'], self.paths['ENTRY_CKPT'], allow_mass_transfer=True)
            policy.release_mode = self.execution['release_mode']
            policy.near_fruit_arm_scale = self._execution_number('near_fruit_arm_scale', 1., 0., 1.)
            policy.block_transport_opening = bool(self.execution.get('block_transport_opening', False))
            policy.diagnostic_transport_scale = self._execution_number('transport_initial_scale', .25, 0., 1.)
            policy.diagnostic_transport_ramp_s = self._execution_number('transport_ramp_s', 3., 0., 60.)
            self.policy = policy
        else:
            self.policy.env = state
        self.state = state
        self.policy.reset()
        state.transport_adaptive_grip = state.settings.transport_adaptive_grip
        state.transport_pose_stop = state.settings.transport_pose_stop
        self.target_id = target_id
        self._last_control_time = None
        self._cancelled = False
        self._diagnostic_tick = 0
        self._diagnostic_trace = self._diagnostic_capture = None
        self._install_diagnostic_hooks()

    def _execution_number(self, name: str, default: float, low: float, high: float) -> float:
        value = finite_scalar(self.execution.get(name, default), name)
        if not low <= value <= high:
            raise ValueError(f'Invalid Teacher action_execution {name}')
        return value

    @torch.no_grad()
    def tick(self, sample: Mapping, dt_s: float = CONTROL_DT) -> TeacherStep:
        """이전 명령 결과를 먼저 평가하고 RUNNING일 때 다음20Hz 명령을 계산합니다."""
        if self.state is None or self.policy is None:
            raise RuntimeError('start_target must precede tick')
        if not math.isclose(finite_scalar(dt_s, 'dt_s'), CONTROL_DT, rel_tol=0., abs_tol=1e-10):
            raise ValueError('Teacher tick period must be exactly0.05 simulation seconds')
        now = finite_scalar(sample['time_s'], 'time_s')
        if self._last_control_time is not None and not math.isclose(now - self._last_control_time,
                CONTROL_DT, rel_tol=0., abs_tol=1e-6):
            raise ValueError('Teacher samples must advance by0.05 simulation seconds per tick')
        self.state.accept_sample(sample)
        if self.state._has_action and self.state.assignment_status == 'RUNNING' and not self._cancelled:
            self.state.finish_control_interval()
        previous_time = self._last_control_time
        self._last_control_time = now
        trace = None
        self._diagnostic_tick += 1
        if self._diagnostic_enabled:
            trace = dict(schema_version=1, source='actual_forward_hooks', kind='control_tick',
                target_id=self.target_id, time_s=now, policy_tick_index=self._diagnostic_tick,
                requested_control_dt_s=float(dt_s),
                actual_control_dt_s=None if previous_time is None else now-previous_time,
                policy_executed=False, expert_calls={}, state_before=self._diagnostic_state(),
                observation_frame='fixed_legacy_policy_frame', quaternion_order='wxyz',
                observation_layout_source='farm_sim_devices/_teacher_vendor/kernel.py:TeacherKernel._get_observations',
                observation_layout=DIAGNOSTIC_OBSERVATION_LAYOUT,
                expert_time_slot=42)
        if self.state.assignment_status == 'RUNNING' and not self._cancelled and not self.state.physical_success:
            observation = self.state.observation()
            if trace is not None:
                trace['observation_raw'] = self._diagnostic_value(observation['policy'])
            self._diagnostic_capture = trace
            try:
                action = self.policy(observation)
            finally:
                self._diagnostic_capture = None
            if action.shape != (1, 6) or not bool(torch.isfinite(action).all()):
                raise ValueError('Teacher must return finite(1,6) normalized increments')
            clipped = action.clamp(-1., 1.)
            if trace is not None:
                selected = int(self.state.expert_stage[0])
                captured = trace['expert_calls'][str(selected)]
                trace.update(policy_executed=True, selected_expert=selected,
                    observation_expert=captured['normalizer_input'],
                    observation_normalized=captured['normalizer_output'],
                    expert_raw_action=captured['actor_output'],
                    staged_action=self._diagnostic_value(action),
                    clipped_action=self._diagnostic_value(clipped))
            self.state.prepare_action(clipped)
        if trace is not None:
            after = self._diagnostic_state()
            before_stage, after_stage = trace['state_before']['expert_stage'], after['expert_stage']
            trace.update(state_after=after, stage_changed=before_stage != after_stage,
                stage_transition=dict(previous=before_stage, current=after_stage, time_s=now,
                    reason_source='derived_from_observed_stage_change',
                    reason='unchanged' if before_stage == after_stage else
                           f'expert_{before_stage}_to_{after_stage}'),
                final_action=self._diagnostic_value(self.state.actions),
                joint_targets=self._diagnostic_value(self.state.targets),
                joint_targets_semantics='new_policy_target' if trace['policy_executed']
                                        else 'held_previous_policy_target')
            self._diagnostic_trace = trace
        return self._result()

    @torch.no_grad()
    def observe(self, sample: Mapping) -> TeacherStep:
        """복귀/안착 중 실제 과실 결과만 갱신합니다. 새 정책 명령은 생성하지 않습니다."""
        if self.state is None:
            raise RuntimeError('No assigned target to observe')
        self.state.accept_sample(sample)
        if self._diagnostic_enabled:
            self._diagnostic_trace = dict(schema_version=1, source='measured_state_only', kind='observe',
                target_id=self.target_id, time_s=float(sample['time_s']), policy_executed=False,
                expert_calls={}, state_after=self._diagnostic_state(),
                held_action=self._diagnostic_value(self.state.actions),
                held_joint_targets=self._diagnostic_value(self.state.targets))
        return self._result()

    def cancel(self) -> None:
        """취소를 latch합니다. 물리적 정지/복귀 확인은 device가 수행해야 합니다."""
        self._cancelled = True

    def _result(self) -> TeacherStep:
        assert self.state is not None
        status = ('CANCELLED' if self._cancelled else 'SUCCEEDED' if self.state.physical_success
                  else self.state.assignment_status)
        reason = ('operator_cancel' if self._cancelled else 'physical_basket_settled'
                  if self.state.physical_success else self.state.failure_reason())
        if status == 'SUCCEEDED' and not reason:
            reason = 'teacher_strict_harvest_confirmed'
        stage = int(self.state.expert_stage[0]) if hasattr(self.state, 'expert_stage') else -1
        diagnostics = self.state.diagnostics()
        diagnostics.update(target_id=self.target_id, action=self.state.actions[0].cpu().tolist(),
                           joint_order=list(JOINT_NAMES))
        if self._diagnostic_enabled and self._diagnostic_trace is not None:
            diagnostics['diagnostic_trace'] = copy.deepcopy(self._diagnostic_trace)
        return TeacherStep(self.state.targets[0].cpu().tolist(), status, reason, stage, diagnostics)
