"""시뮬 전용 정차 위치 수확: 후보1회, 실제 복귀, 누적 결과와 취소를 관리합니다.

World.step/reset, 과실 삭제·재배치, 관절 순간이동을 호출하지 않습니다. 20Hz는
시뮬 시간, UDP lease는 wall 시간이며 한 번 완료한 job을 재전송으로 다시 실행하지 않습니다.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np


def _json(value: Any) -> Any:
    """측정 ndarray를 로그용 값으로 바꿉니다."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def reverse_measured_path(history: list, home: np.ndarray, spacing: float = .025) -> np.ndarray:
    """전달 return_path의 역방향 경유점 규칙입니다. 충돌 없는 경로라는 보장은 없습니다."""
    values = np.asarray(history, dtype=float)
    if values.ndim != 2 or values.shape[1] != 6 or not len(values) or not np.isfinite(values).all():
        raise ValueError('유한한 측정 관절 이력 Nx6가 필요합니다.')
    path = []
    for point in values[::-1]:
        point = point.copy()
        point[-1] = home[-1]
        if not path or np.max(np.abs(point[:5]-path[-1][:5])) >= spacing:
            path.append(point)
    path.append(np.asarray(home, dtype=float).copy())
    return np.asarray(path)


class PhysicalReturn:
    """측정 복귀 경로 또는 지정 자세 경로를 따라간다. 접촉·시간 초과 시 정지한다."""

    def __init__(self, device: Any, history: list, config: Mapping, now: float,
                 *, path: np.ndarray | None = None) -> None:
        self.device, self.config = device, config
        current = device.joint_positions()
        self.path = (reverse_measured_path(history+[current.copy()], device.home) if path is None
                     else np.asarray(path, dtype=float).copy())
        if path is not None and (self.path.ndim != 2 or self.path.shape[1] != 6 or not len(self.path)
                or not np.isfinite(self.path).all() or np.any(self.path < device.lower)
                or np.any(self.path > device.upper)):
            raise ValueError('전환 경로는 관절 한계 내의 유한한 Nx6 배열이어야 합니다.')
        self.index, self.start, self.waypoint_start, self.stable = 0, now, now, 0.
        self.previous, self.command = current.copy(), current.copy()
        self.bias = np.zeros(6)
        self.problem = ''
        self.peak_force = 0.

    def observe_physics(self) -> None:
        """제어 간격 사이의 실제 충돌도 latch합니다."""
        force = self.device.contacts_for_recovery()['max_force_N']
        self.peak_force = max(self.peak_force, force)
        if force > self.config['recovery_contact_limit_N']:
            self.problem = f'return_contact_{force:.3f}N'

    def tick(self, now: float, dt: float) -> tuple[str, str]:
        """명령 목표만 쓰며 시간 진행은 호출자가 담당합니다."""
        self.observe_physics()
        if self.problem:
            return 'FAILED', self.problem
        current = self.device.joint_positions()
        measured_speed = float(np.max(np.abs(current-self.previous))/dt)
        self.previous = current.copy()
        goal = self.path[self.index]
        if np.max(np.abs(current-goal)) < .035:
            if self.index < len(self.path)-1:
                self.index += 1
                self.waypoint_start, self.stable = now, 0.
                goal = self.path[self.index]
            else:
                qd = self.device.joint_velocities()
                self.stable = self.stable+dt if measured_speed < .05 and np.max(abs(qd)) < .5 and current[-1] > .65 else 0.
                if self.stable >= .25:
                    self.device.command(current)
                    return 'SUCCEEDED', 'measured_home_open_gripper'
        else:
            self.stable = 0.
        if (now-self.waypoint_start > self.config['recovery_waypoint_timeout_s']
                or now-self.start > self.config['recovery_timeout_s']):
            return 'FAILED', 'return_tracking_stalled'
        self.bias = np.clip(self.bias+.5*(goal-current)*dt, -.06, .06)
        desired = np.clip(goal+self.bias, self.device.lower, self.device.upper)
        step = self.config['recovery_velocity_rad_s']*dt
        self.command += np.clip(desired-self.command, -step, step)
        self.command = np.clip(self.command, current-.08, current+.08)
        self.device.command(np.clip(self.command, self.device.lower, self.device.upper))
        return 'RUNNING', ''


class ArmSession:
    """한 로봇의 시뮬 수확 작업을 소유합니다. 후보/시도 정책은 공통 코드에 두지 않습니다."""

    def __init__(self, session: str, robot_id: str, map_id: str, device: Any,
                 controller: Any, physics: Any, config: Mapping, log_root: Path) -> None:
        self.session, self.robot_id, self.map_id = session, robot_id, map_id
        self.device, self.controller, self.physics, self.config = device, controller, physics, dict(config)
        self.dt = float(self.config['control_dt_s'])
        if not math.isclose(self.dt, .05, abs_tol=1e-10):
            raise ValueError('전달 Teacher는20Hz입니다.')
        self.log_root = Path(log_root)
        self.job: dict | None = None
        self.state = dict(job_id='', status='IDLE', stage='IDLE', success_count=0, failed_count=0,
                          event_seq=0, error_code='', error_message='', safe_stopped=True)
        self._last_seq, self._lease = -1, -math.inf
        self._completed_jobs: dict[str, dict] = {}
        self._completed_requests: dict[str, dict] = {}
        self._all_attempted: set[str] = set()
        self._successful_ids: set[str] = set()
        self._blocked = False
        self._trace = None
        self._directory: Path | None = None
        self._last_tick: float | None = None
        self._target: str | None = None
        self._return: PhysicalReturn | None = None
        self._attempts: list[dict] = []
        self._history: list = []
        self._stop_hold = None
        self._stop_request = ('FAILED', '', '')
        self._stop_stable, self._stop_start = 0., 0.
        self._settle_start = 0.
        self._last_teacher = None
        self._pending_cancel = False
        self._base_stationary = False
        self._candidates: list[dict] = []

    @property
    def attempted_target_ids(self) -> frozenset[str]:
        """시험 UI가 이미 시도한 과실을 재배치 후보에서 제외하도록 읽기 전용 ID를 준다."""
        return frozenset(self._all_attempted)

    @property
    def deposited_target_ids(self) -> frozenset[str]:
        """시험 중 박스에 적재된 과실을 두고 차체만 순간 이동하지 않도록 조회한다."""
        return frozenset(self._successful_ids)

    @property
    def busy(self) -> bool:
        """팔 동작 중 또는 정지 미확인이면 차체 속도 명령도 차단합니다."""
        return self.state['status'] == 'RUNNING' or self._blocked

    @property
    def travel_ready(self) -> bool:
        """접힌 양팔의 실측 상태로 주행 허용 여부를 반환한다."""
        return bool(self.device.travel_ready()) if getattr(self.device, 'travel', None) is not None else True

    def _transition(self, now: float, stage: str, goal: np.ndarray) -> None:
        """정차 중 오른팔만 속도 제한·접촉 감시를 유지하며 자세를 바꾼다."""
        current = self.device.joint_positions()
        # 기존 복귀의 경유점 시간 제한을 지키도록 짧은 관절 공간 경유점으로 나눈다.
        count = max(1, int(np.ceil(np.max(abs(goal-current))/.15)))
        path = np.linspace(current, goal, count+1)[1:]
        self._return = PhysicalReturn(self.device, [], self.config, now, path=path)
        self.device.command(current)
        self.state['stage'] = stage
        self._log(stage, time_s=now, measured_start=current, goal=goal)

    def telemetry(self) -> dict:
        """최종 결과는 새 작업 전까지 반복 전송합니다."""
        return dict(self.state)

    def accept(self, message: Any, now: float | None = None) -> bool:
        """순서·세션·대상을 검사하고 요청만 저장합니다. 여기서는 물리 명령을 쓰지 않습니다."""
        now = time.monotonic() if now is None else now
        if not isinstance(message, dict):
            return False
        seq, sent, job_id, op = (message.get(k) for k in ('seq', 'sent', 'job_id', 'op'))
        if (message.get('kind') != 'harvest_arm' or message.get('session') != self.session
                or message.get('robot_id') != self.robot_id or type(seq) is not int or seq <= self._last_seq
                or type(sent) not in (int, float) or not math.isfinite(sent)
                or not 0 <= now-sent <= self.config['lease_s']
                or not isinstance(job_id, str) or not job_id or len(job_id) > 128
                or any(c not in '0123456789abcdef-' for c in job_id)
                or op not in ('start', 'keepalive', 'cancel', 'ack')):
            return False
        if op == 'start':
            if (message.get('map_id') != self.map_id or not isinstance(message.get('task_id'), str)
                    or not message['task_id'] or not isinstance(message.get('window_id'), str)
                    or type(message.get('expected_count')) is not int or message['expected_count'] < 0):
                return False
            if job_id in self._completed_jobs:
                if any(message.get(key) != self._completed_requests[job_id].get(key)
                       for key in ('task_id', 'window_id', 'expected_count', 'map_id', 'goal_pose')):
                    return False
                if not self.busy:
                    self.state = dict(self._completed_jobs[job_id])
                self._last_seq = seq
                return True
            if self.state['job_id'] == job_id:
                if self.job is None or any(message.get(key) != self.job.get(key)
                        for key in ('task_id', 'window_id', 'expected_count', 'map_id', 'goal_pose')):
                    return False
            elif self.busy:
                return False
            else:
                self.job = dict(message)
                self.state = dict(job_id=job_id, status='RUNNING', stage='PREPARE', success_count=0,
                                  failed_count=0, event_seq=0, error_code='', error_message='', safe_stopped=False)
                self._pending_cancel = False
                self._last_tick, self._target, self._return = None, None, None
                self._attempts, self._history, self._candidates = [], [], []
                self._last_teacher = None
        elif job_id != self.state['job_id']:
            return False
        self._last_seq, self._lease = seq, float(sent)
        if op == 'cancel' and self.state['status'] == 'RUNNING':
            self._pending_cancel = True
        return True

    def _log(self, event: str, **values: Any) -> None:
        if self._trace is not None:
            self._trace.write(json.dumps(dict(event=event, **values), ensure_ascii=False, default=_json)+'\n')
            self._trace.flush()

    def _open_log(self, now: float) -> None:
        self._directory = self.log_root/self.session/self.state['job_id']
        self._directory.mkdir(parents=True, exist_ok=True)
        self._trace = (self._directory/'trace.jsonl').open('w')
        (self._directory/'request.json').write_text(json.dumps(self.job, ensure_ascii=False, indent=2)+'\n')
        profile = getattr(self.controller, 'profile', None)
        if profile is not None:
            (self._directory/'profile.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2, default=_json)+'\n')
        artifacts = getattr(self.controller, 'artifact_manifest', None)
        if artifacts is not None:
            (self._directory/'artifact_sha256.json').write_text(json.dumps(artifacts, indent=2)+'\n')
        self._log('START', time_s=now)

    def _stop(self, now: float, status: str, code: str, reason: str) -> None:
        if self.state['stage'] == 'STOPPING':
            return
        self.controller.cancel()
        self._stop_hold = np.clip(self.device.joint_positions(), self.device.lower, self.device.upper)
        self._stop_previous = self.device.joint_positions().copy()
        self.device.command(self._stop_hold)
        self._stop_request = (status, code, reason)
        self._stop_start, self._stop_stable = now, 0.
        self.state['stage'] = 'STOPPING'
        self._log('STOP_REQUEST', time_s=now, status=status, reason=reason)

    def _finish(self, now: float, status: str, code: str = '', reason: str = '', *, safe: bool = True) -> None:
        # 시도 후 복귀 실패도 한 번의 시도 결과를 남깁니다. 사용자 취소는 진행중 시도를 집계하지 않습니다.
        if self._target is not None and status != 'CANCELED' and not self._pending_cancel:
            success = bool(safe and self._last_teacher is not None and
                           self._last_teacher.diagnostics.get('physical_status') == 'SUCCEEDED')
            self._record_attempt(now, success, reason or code)
        self.state.update(status=status, stage='DONE', error_code=code, error_message=reason, safe_stopped=safe)
        self.state['event_seq'] += 1
        self._blocked = not safe or not self.travel_ready
        self.physics.set_activity(self.robot_id, self._blocked)
        self._completed_jobs[self.state['job_id']] = dict(self.state)
        self._completed_requests[self.state['job_id']] = dict(self.job)
        self._log('RESULT', time_s=now, **self.state)
        if self._directory:
            (self._directory/'result.json').write_text(json.dumps(dict(self.state, attempts=self._attempts,
                candidate_count=len(self._candidates)), ensure_ascii=False, indent=2, default=_json)+'\n')
        if self._trace:
            self._trace.close()
            self._trace = None
        self.device.clear_target()
        self._target = None

    def _record_attempt(self, now: float, success: bool, reason: str, sample: Mapping | None = None) -> None:
        record = dict(target_id=self._target, success=success, time_s=now, reason=reason,
            teacher_strict_success=bool(self._last_teacher is not None and
                self._last_teacher.diagnostics.get('teacher_strict_success', False)))
        if self._last_teacher is not None:
            record.update({key: self._last_teacher.diagnostics.get(key) for key in
                ('physical_status', 'physical_in_box', 'physical_place_hold_s')})
        if sample is not None:
            record.update(attached=bool(sample['attached']), fruit_position=np.asarray(sample['fruit_position']).tolist())
        self._attempts.append(record)
        if success:
            self._successful_ids.add(self._target)
        self.state['success_count' if success else 'failed_count'] += 1
        self.state['event_seq'] += 1
        self._log('ATTEMPT_RESULT', **record)

    def observe_physics_tick(self, dt_s: float, sim_time_s: float) -> None:
        """스케줄러의 실제 물리 tick 뒤에만 호출합니다. 수확 중 접촉 정지 요청을 latch합니다."""
        if self._blocked:
            return
        try:
            self.device.observe_physics_tick(dt_s, sim_time_s)
            if (self.state['status'] == 'RUNNING'
                    and self.state['stage'] in ('RETURNING', 'DEPLOYING', 'STOWING') and self._return):
                self._return.observe_physics()
                if self._return.problem:
                    code = 'RETURN_FAILED' if self.state['stage'] == 'RETURNING' else 'ARM_TRANSITION_FAILED'
                    self._stop(sim_time_s, 'FAILED', code, self._return.problem)
        except Exception as error:
            if self.state['status'] != 'RUNNING':
                raise
            self._handle_error(sim_time_s, error)

    def _next_target(self, now: float) -> None:
        remaining = [item for item in self._candidates if item['target_id'] not in self._all_attempted]
        if not remaining:
            if getattr(self.device, 'travel', None) is not None:
                self._transition(now, 'STOWING', self.device.travel)
            else:
                self._stop(now, 'SUCCESS', '', 'current_window_candidates_processed')
            return
        target = remaining[0]['target_id']
        self._all_attempted.add(target)
        available = set(self.device.candidate_ids(self._all_attempted-{target}))
        if target not in available:
            self._attempts.append(dict(target_id=target, success=False, reason='target_no_longer_available', time_s=now))
            self.state['failed_count'] += 1
            self.state['event_seq'] += 1
            self.state['stage'] = 'NEXT'
            return
        self.device.select_target(target, self._all_attempted-{target})
        sample = self.device.sample()
        self.controller.start_target(target, sample)
        self._target, self._history = target, [np.asarray(sample['q']).copy()]
        self._last_teacher = None
        self.state['stage'] = 'POLICY'
        self._log('TARGET', time_s=now, target_id=target, sample=sample)
        self._policy_tick(now, sample)

    def _policy_tick(self, now: float, sample: Mapping) -> None:
        step = self.controller.tick(sample, self.dt)
        self._last_teacher = step
        self._history.append(np.asarray(sample['q']).copy())
        self._log('POLICY', time_s=now, target_id=self._target, status=step.status,
                  stage=step.stage, reason=step.reason, joint_targets=step.joint_targets,
                  diagnostics=step.diagnostics, sample={k:v for k,v in sample.items() if k != 'collision_vertices'})
        if step.status == 'RUNNING':
            self.device.configure_actuator(step.diagnostics['actuator'])
            self.device.command(step.joint_targets)
        else:
            self.device.restore_actuator()
            self._return = PhysicalReturn(self.device, self._history, self.config, now)
            self.state['stage'] = 'RETURNING'
            # 정책의 마지막 증분을 유지하지 않고 실제 위치에서 복귀 목표를 시작합니다.
            self.device.command(self.device.joint_positions())

    def tick(self, now: float, *, base_stationary: bool, wall_now: float | None = None) -> None:
        """렌더 프레임마다 호출해도 실제 제어는 시뮬0.05초마다 한 번만 실행합니다."""
        if self.state['status'] != 'RUNNING':
            return
        wall_now = time.monotonic() if wall_now is None else wall_now
        if self._last_tick is not None and now-self._last_tick < self.dt-1e-8:
            return
        try:
            if self._last_tick is not None and not math.isclose(now-self._last_tick, self.dt, abs_tol=1e-6):
                self._stop(now, 'FAILED', 'CONTROL_TIME_JUMP', 'teacher_control_interval_changed')
            self._last_tick = now
            self._tick(now, bool(base_stationary), wall_now)
        except Exception as error:
            self._handle_error(now, error)

    def _handle_error(self, now: float, error: Exception) -> None:
        """정지 측정 자체가 고장 나면 반복 RUNNING으로 남기지 않고 미확인 종료합니다."""
        self._log('EXCEPTION', time_s=now, error=repr(error))
        if self.state['stage'] == 'STOPPING':
            self._finish(now, 'FAILED', 'CANCEL_UNCONFIRMED', str(error), safe=False)
            return
        try:
            self._stop(now, 'FAILED', 'ARM_RUNTIME_ERROR', str(error))
        except Exception as stop_error:
            self._finish(now, 'FAILED', 'CANCEL_UNCONFIRMED', str(stop_error), safe=False)

    def _tick(self, now: float, stationary: bool, wall_now: float) -> None:
        if self.state['stage'] == 'PREPARE':
            self._open_log(now)
            self.physics.set_activity(self.robot_id, True)
            if not stationary:
                self._stop(now, 'FAILED', 'BASE_MOVING', 'base_not_stationary_at_start')
            elif getattr(self.device, 'travel', None) is not None and self.travel_ready:
                self._transition(now, 'DEPLOYING', self.device.home)
            elif (np.max(abs(self.device.joint_positions()-self.device.home)) > .06
                  or np.max(abs(self.device.joint_velocities())) > .5):
                self._stop(now, 'FAILED', 'ARM_NOT_HOME', 'initial_measured_home_required')
            else:
                # 다음 프레임의 prepare_frame에서 지역 물리가 켜진 뒤 후보를 선택합니다.
                self.state['stage'] = 'SELECT'
        if self._pending_cancel:
            self._stop(now, 'CANCELED', '', 'operator_cancel')
        elif wall_now-self._lease > self.config['lease_s']:
            self._stop(now, 'FAILED', 'ARM_LEASE_EXPIRED', 'sim_arm_request_heartbeat_lost')
        elif not stationary:
            self._stop(now, 'FAILED', 'BASE_MOVING', 'base_moved_during_harvest')
        if self._successful_ids and self.state['stage'] != 'STOPPING':
            escaped = self.device.escaped_deposits(self._successful_ids)
            if escaped:
                self._stop(now, 'FAILED', 'PREVIOUS_DEPOSIT_LOST', ','.join(escaped))
        stage = self.state['stage']
        if stage == 'STOPPING':
            if self._target is not None:
                self._last_teacher = self.controller.observe(self.device.sample())
            self.device.command(self._stop_hold)
            qd = self.device.joint_velocities()
            q = self.device.joint_positions()
            measured_speed = np.max(abs(q-self._stop_previous))/self.dt
            self._stop_previous = q.copy()
            # 60Hz PhysX의 solver 속도와 실제 pose 차분을 함께 확인한다.
            # 복귀와 동일한 .05rad/s pose / .5rad/s SDK 기준이며 목표 이탈도 거부한다.
            slow = (np.isfinite(qd).all() and np.isfinite(q).all()
                    and measured_speed < .05 and np.max(abs(qd)) < .5
                    and np.max(abs(q-self._stop_hold)) < .035 and stationary)
            self._stop_stable = self._stop_stable+self.dt if slow else 0.
            if self._stop_stable >= self.config['stop_hold_s']:
                if self._stop_request[0] == 'SUCCESS' and self._successful_ids:
                    escaped = self.device.escaped_deposits(self._successful_ids)
                    if escaped:
                        self._stop_request = ('FAILED', 'PREVIOUS_DEPOSIT_LOST', ','.join(escaped))
                if self._stop_request[0] == 'SUCCESS' and not self.travel_ready:
                    self._stop_request = ('FAILED', 'ARM_NOT_STOWED', 'both_arms_travel_pose_required')
                self._finish(now, *self._stop_request)
            elif now-self._stop_start >= self.config['stop_timeout_s']:
                self._finish(now, 'FAILED', 'CANCEL_UNCONFIRMED', 'measured_stop_not_confirmed', safe=False)
            return
        if stage in ('DEPLOYING', 'STOWING'):
            status, reason = self._return.tick(now, self.dt)
            if status == 'FAILED':
                self._stop(now, 'FAILED', 'ARM_TRANSITION_FAILED', reason)
            elif status == 'SUCCEEDED':
                if stage == 'DEPLOYING':
                    self.state['stage'] = 'SELECT'
                elif self.travel_ready:
                    self._stop(now, 'SUCCESS', '', 'current_window_candidates_processed_arms_stowed')
                else:
                    self._stop(now, 'FAILED', 'ARM_NOT_STOWED', 'both_arms_travel_pose_required')
            return
        if stage == 'SELECT':
            # PREPARE와 같은 tick에서 선택하지 않도록 다음 제어 간격까지 기다립니다.
            if not hasattr(self, '_select_job') or self._select_job != self.state['job_id']:
                self._select_job = self.state['job_id']
                return
            self._candidates = sorted(self.device.candidates(self._all_attempted),
                key=lambda item:(item['root_world_m'][2], item['target_id']))
            self._log('CANDIDATES', time_s=now, candidates=self._candidates)
            self._next_target(now)
            return
        if stage == 'NEXT':
            self._next_target(now)
            return
        if self._target is None:
            return
        sample = self.device.sample()
        if (sample['dock_displacement_m'] > self.config['base_drift_limit_m']
                or sample['dock_rotation_delta_rad'] > self.config['base_yaw_drift_limit_rad']):
            self._stop(now, 'FAILED', 'BASE_DRIFT', 'right_arm_mount_moved_from_dock')
            return
        if sample.get('other_detached', False):
            self._stop(now, 'FAILED', 'NON_TARGET_DETACHED', 'unattempted_neighbor_detached')
            return
        if stage == 'POLICY':
            self._policy_tick(now, sample)
            return
        self._last_teacher = self.controller.observe(sample)
        if stage == 'RETURNING':
            status, reason = self._return.tick(now, self.dt)
            if status == 'FAILED':
                self._stop(now, 'FAILED', 'RETURN_FAILED', reason)
            elif status == 'SUCCEEDED':
                self.state['stage'], self._settle_start = 'SETTLING', now
            return
        if stage == 'SETTLING':
            success = self._last_teacher.diagnostics.get('physical_status') == 'SUCCEEDED'
            if not success and now-self._settle_start < self.config['settle_s']:
                return
            self._record_attempt(now, success,
                'physical_basket_settled' if success else self._last_teacher.reason or 'not_settled_in_basket', sample)
            self.device.clear_target()
            self._target, self._return = None, None
            self.state['stage'] = 'NEXT'

    def close(self) -> None:
        """종료 로그만 닫습니다. 미완료 작업을 성공으로 만들지 않습니다."""
        if self._trace:
            self._log('PROCESS_EXIT', state=self.state)
            self._trace.close()
            self._trace = None
