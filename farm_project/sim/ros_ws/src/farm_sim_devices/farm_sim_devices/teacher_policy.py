"""60Hz 전달 Teacher의 JIT 추론과 원본 단계 제어. 농장 scene을 생성/reset하지 않는다."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping
import torch
from .teacher_state import TeacherState, CONTROL_DT, JOINT_NAMES, finite_scalar

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
    joint_targets: list[float]
    status: str
    reason: str
    stage: int
    diagnostics: dict


class TeacherController:
    """정규화를 포함한 JIT를 로드하고 목표별 계산 상태만 새로 만든다."""

    def __init__(self, profile: Mapping, *, project_root: Path, device: str = 'cpu') -> None:
        self.profile = dict(profile)
        self.project_root = Path(project_root).resolve()
        self.device = torch.device(device)
        # Batch-one CPU Teacher 제어는 큰 intra-op pool보다 단일 스레드가 빠르다.
        if self.device.type == 'cpu':
            torch.set_num_threads(1)
        path = (self.project_root/profile['deployment']).resolve()
        if not path.is_relative_to(self.project_root / 'sim'):
            raise ValueError('Teacher 전달 설정은 sim 내부에 있어야 합니다.')
        self.deployment = json.loads(path.read_text())
        if self.deployment['runtime'] != 'teacher60_finger_friction_run_v2':
            raise ValueError('검증된 60Hz r2 실행 구성만 지원합니다.')
        if profile['runtime'] != self.deployment['task']:
            raise ValueError('Teacher runtime과 DEPLOYMENT.json이 다릅니다.')
        self.runtime = dict(self.deployment['task'])
        self.joint_limits = dict(profile['joint_limits'])
        self.kinematics_path = path.parent/'harvest_training.urdf'
        self.actors = {}
        self.paths = {}
        for name, row in self.deployment['actors'].items():
            actor_path = (path.parent/'actors'/row['path']).resolve()
            if not actor_path.is_relative_to(self.project_root):
                raise ValueError('모델은 프로젝트 내부에 있어야 합니다.')
            if hashlib.sha256(actor_path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Teacher artifact hash mismatch: '+str(actor_path))
            self.paths[name] = actor_path
            self.actors[name] = torch.jit.load(str(actor_path), map_location=self.device).eval()
        self.artifact_manifest = {str(p.relative_to(self.project_root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [path, self.kinematics_path, *self.paths.values()]}
        self.state = None
        self.target_id = None
        self._cancelled = False
        self._last_control_time = None
        self._diagnostic_enabled = False
        self._calls = {}
        self._trace = None
        self._tick_index = 0

    def enable_diagnostic_trace(self, enabled: bool = True) -> None:
        if type(enabled) is not bool:
            raise ValueError('진단 활성화 값은 bool이어야 합니다.')
        self._diagnostic_enabled = enabled

    def _infer(self, name: str, observation: dict) -> torch.Tensor:
        raw = observation['policy']
        action = self.actors[name](raw)
        if action.shape != (1, 6) or not torch.isfinite(action).all():
            raise ValueError('Teacher 출력은 유한한 (1,6)이어야 합니다.')
        if self._diagnostic_enabled:
            self._calls[name] = dict(observation_raw=raw[0].detach().cpu().tolist(),
                                    actor_output=action[0].detach().cpu().tolist(),
                                    normalization='embedded_in_torchscript')
        return action

    def start_target(self, target_id: str, initial_sample: Mapping) -> None:
        if not isinstance(target_id, str) or not target_id:
            raise ValueError('persistent target_id is required')
        self.state = TeacherState(self.runtime, self.joint_limits, initial_sample,
            device=str(self.device), deployment=self.deployment, kinematics_path=self.kinematics_path,
            grasp_policy=lambda obs: self._infer('grasp', obs),
            transport_policy=lambda obs: self._infer('transport_reference', obs))
        if not bool(self.state.attached[0, 0]):
            raise ValueError('Teacher target must still be attached at assignment')
        self.target_id = target_id
        self._last_control_time = None
        self._cancelled = False
        self._trace = None
        self._tick_index = 0

    @torch.no_grad()
    def tick(self, sample: Mapping, dt_s: float = CONTROL_DT) -> TeacherStep:
        if self.state is None:
            raise RuntimeError('start_target must precede tick')
        if not math.isclose(finite_scalar(dt_s, 'dt_s'), CONTROL_DT, rel_tol=0., abs_tol=1e-10):
            raise ValueError('Teacher tick period must be exactly0.05 simulation seconds')
        now = finite_scalar(sample['time_s'], 'time_s')
        if self._last_control_time is not None and not math.isclose(now-self._last_control_time,
                CONTROL_DT, rel_tol=0., abs_tol=1e-6):
            raise ValueError('Teacher samples must advance by0.05 simulation seconds per tick')
        self.state.accept_sample(sample)
        if self.state._has_action and self.state.assignment_status == 'RUNNING' and not self._cancelled:
            self.state.finish_control_interval()
        self._last_control_time = now
        self._tick_index += 1
        self._calls = {}
        executed = self.state.assignment_status == 'RUNNING' and not self._cancelled
        if executed:
            self.state.prepare_action(self._infer('pull', self.state.observation()))
        if self._diagnostic_enabled:
            self._trace = dict(schema_version=2, source='actual_torchscript_calls', kind='control_tick',
                time_s=now, target_id=self.target_id, policy_tick_index=self._tick_index,
                requested_control_dt_s=dt_s, policy_executed=executed, expert_calls=self._calls,
                observation_layout=DIAGNOSTIC_OBSERVATION_LAYOUT, quaternion_order='wxyz',
                joint_targets=self.state.targets[0].cpu().tolist(),
                final_action=self.state.actions[0].cpu().tolist(),
                state_after=self.state.diagnostics())
        return self._result()

    @torch.no_grad()
    def observe(self, sample: Mapping) -> TeacherStep:
        if self.state is None:
            raise RuntimeError('No assigned target to observe')
        self.state.accept_sample(sample)
        self._trace = None
        return self._result()

    def cancel(self) -> None:
        self._cancelled = True

    def _result(self) -> TeacherStep:
        state = self.state
        status = 'CANCELLED' if self._cancelled else state.assignment_status
        reason = 'operator_cancel' if self._cancelled else state.failure_reason()
        stage = 2 if state.deposit_active[0] else 1 if state.transport_active[0] else 0 if state.pull_active[0] else -1
        diagnostics = state.diagnostics()
        diagnostics.update(target_id=self.target_id, action=state.actions[0].cpu().tolist(), joint_order=list(JOINT_NAMES))
        if self._diagnostic_enabled and self._trace is not None:
            diagnostics['diagnostic_trace'] = self._trace
        return TeacherStep(state.targets[0].cpu().tolist(), status, reason, stage, diagnostics)
