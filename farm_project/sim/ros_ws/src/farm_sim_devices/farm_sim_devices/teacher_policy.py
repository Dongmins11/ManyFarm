"""검증한 4개 Teacher 정책의 CPU 추론과 농장 순수 상태 어댑터.

물리 step·관절 순간이동·ROS 호출은 없습니다. root runtime가20Hz에 tick하고
반환한6개 joint target만 device로 보냅니다. 실패 뒤 다음 목표 선택은 coordinator 책임입니다.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import torch

from .teacher_state import TeacherState, CONTROL_DT, JOINT_NAMES, finite_scalar
from ._teacher_vendor.staged_teacher import StagedTeacher


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
        self._last_control_time = now
        if self.state.assignment_status == 'RUNNING' and not self._cancelled and not self.state.physical_success:
            action = self.policy(self.state.observation())
            if action.shape != (1, 6) or not bool(torch.isfinite(action).all()):
                raise ValueError('Teacher must return finite(1,6) normalized increments')
            self.state.prepare_action(action.clamp(-1., 1.))
        return self._result()

    @torch.no_grad()
    def observe(self, sample: Mapping) -> TeacherStep:
        """복귀/안착 중 실제 과실 결과만 갱신합니다. 새 정책 명령은 생성하지 않습니다."""
        if self.state is None:
            raise RuntimeError('No assigned target to observe')
        self.state.accept_sample(sample)
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
        return TeacherStep(self.state.targets[0].cpu().tolist(), status, reason, stage, diagnostics)
