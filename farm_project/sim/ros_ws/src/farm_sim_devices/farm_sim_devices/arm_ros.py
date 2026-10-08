"""ROS 내부 HarvestTask를 시뮬 UDP 작업에 연결합니다. 수확 판정은 하지 않습니다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import threading
import time
from typing import Any, Mapping


@dataclass(frozen=True)
class ArmRosSettings:
    endpoint: str = 'sim/harvest_arm'
    keepalive_hz: float = 10.
    start_retry_s: float = .2
    execution_timeout_s: float = 180.
    cancel_timeout_s: float = 5.
    status_timeout_s: float = 2.

    @classmethod
    def from_mapping(cls, values: Mapping) -> 'ArmRosSettings':
        """시간 제한은 ROS 시뮬 시간이 아닌 wall 초입니다."""
        settings = cls(**{key: values[key] for key in cls.__dataclass_fields__ if key in values})
        if not isinstance(settings.endpoint, str) or not settings.endpoint or any(c.isspace() for c in settings.endpoint):
            raise ValueError('harvest_arm.endpoint가 비어 있거나 공백을 포함합니다.')
        for key in cls.__dataclass_fields__:
            if key == 'endpoint':
                continue
            value = getattr(settings, key)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('harvest_arm.'+key+'는 유한한 양수여야 합니다.')
        return settings


def goal_fields(goal: Any, config: Mapping) -> dict:
    """원본 ID와 예상 수량을 보존하고 평면 목표만 UDP에 표현합니다."""
    task = goal.harvest_task
    pose, position = task.goal_pose, task.goal_pose.position
    if (goal.robot_id != config['robot_id'] or goal.map_id != config['map_id']
            or any(not isinstance(v, str) or not v.strip() for v in (task.task_id, task.window_id))
            or type(task.expected_count) is not int or task.expected_count < 0
            or pose.frame_id != 'map' or abs(position.z) > .1
            or not all(math.isfinite(v) for v in (position.x, position.y, position.z, pose.yaw))):
        raise ValueError('팔 작업 ID/지도/목표 pose/예상 수량 오류')
    return dict(robot_id=goal.robot_id, map_id=goal.map_id, task_id=task.task_id,
                window_id=task.window_id, expected_count=task.expected_count,
                goal_pose=dict(x=position.x, y=position.y, yaw=pose.yaw))


def valid_status(value: Any) -> bool:
    """잘못된 팔 상태가 정상 바퀴·센서 패킷까지 중단시키지 않게 별도 검증합니다."""
    return (isinstance(value, dict) and isinstance(value.get('job_id'), str)
            and value.get('status') in ('RUNNING', 'SUCCESS', 'FAILED', 'CANCELED')
            and all(type(value.get(k)) is int and value[k] >= 0
                    for k in ('success_count', 'failed_count', 'event_seq'))
            and all(isinstance(value.get(k), str) for k in ('stage', 'error_code', 'error_message'))
            and type(value.get('safe_stopped')) is bool)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArmRosServer:
    """한 goal만 수락하고 Condition으로 대기하여 poll/timer 스레드를 비워 둡니다."""

    def __init__(self, node: Any, config: Mapping) -> None:
        from rclpy.action import ActionServer, GoalResponse, CancelResponse
        from rclpy.callback_groups import ReentrantCallbackGroup
        from farm_interfaces.action import HarvestTask

        self.node, self.settings = node, ArmRosSettings.from_mapping(config)
        self.action_type, self.goal_response, self.cancel_response = HarvestTask, GoalResponse, CancelResponse
        self.condition = threading.Condition()
        self._busy = self._blocked = self._stopping = False
        self._active: dict | None = None
        self._completed: dict[tuple[str, str], dict] = {}
        self.callback_group = ReentrantCallbackGroup()
        self.server = ActionServer(node, HarvestTask, self.settings.endpoint,
            execute_callback=self.execute, goal_callback=self.accept, cancel_callback=self.cancel,
            callback_group=self.callback_group)

    def _live(self, now: float) -> bool:
        return (self.node.session is not None
                and 0 <= now-self.node.last_seen <= self.node.config['runtime']['transport_timeout_s'])

    def accept(self, goal: Any) -> Any:
        try:
            goal_fields(goal, self.node.config)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            self.node.get_logger().warning('시뮬 팔 작업 거절: '+str(error))
            return self.goal_response.REJECT
        with self.condition:
            if self._busy or self._blocked or self._stopping or not self._live(time.monotonic()):
                return self.goal_response.REJECT
            # execute 콜백이 시작되기 전에도 중복 수락을 막습니다.
            self._busy = True
        return self.goal_response.ACCEPT

    def cancel(self, handle: Any) -> Any:
        with self.condition:
            self.condition.notify_all()
        return self.cancel_response.ACCEPT

    def _send(self, job: Mapping, operation: str) -> None:
        self.node.transport.send(dict(job['fields'], kind='harvest_arm', op=operation,
            session=job['session'], robot_id=self.node.config['robot_id'], job_id=job['job_id'],
            seq=time.monotonic_ns(), sent=time.monotonic()))

    def observe(self, session: str, state: Any) -> None:
        """ros_adapter가 세션·순서·시각을 검증한 state 안의 arm만 전달합니다."""
        if not isinstance(state, dict):
            return
        acknowledgement = None
        with self.condition:
            key = (session, state.get('job_id'))
            if valid_status(state) and state['status'] != 'RUNNING' and key in self._completed:
                acknowledgement = self._completed[key]
            job = self._active
            if job is not None and key == (job['session'], job['job_id']):
                if not valid_status(state):
                    job['protocol_error'] = '팔 상태 형식 오류'
                elif state['event_seq'] < job['event_seq']:
                    return
                elif (state['success_count'] < job['counts'][0] or state['failed_count'] < job['counts'][1]):
                    job['protocol_error'] = '팔 누적 수량 역행'
                else:
                    job['counts'] = (state['success_count'], state['failed_count'])
                    job['event_seq'], job['state'] = state['event_seq'], dict(state)
                    job['last_seen'] = time.monotonic()
                self.condition.notify_all()
        if acknowledgement is not None:
            self._send(acknowledgement, 'ack')

    def _feedback(self, handle: Any, counts: tuple[int, int]) -> None:
        feedback = self.action_type.Feedback()
        feedback.robot_id, feedback.task_id = handle.request.robot_id, handle.request.harvest_task.task_id
        feedback.success_count, feedback.failed_count = counts
        feedback.timestamp = _timestamp()
        handle.publish_feedback(feedback)

    def execute(self, handle: Any) -> Any:
        """start 재전송/lease 갱신/취소는 wall 시간으로 진행합니다."""
        now = time.monotonic()
        job = dict(fields=goal_fields(handle.request, self.node.config), session=self.node.session,
            job_id=bytes(handle.goal_id.uuid).hex(), counts=(0, 0), event_seq=-1,
            state=None, last_seen=now, protocol_error='')
        with self.condition:
            self._active = job
        next_send, began, cancel_started = 0., now, None
        published = None
        cause, detail = '', ''
        code, error_code, error_message = 'FAILED', 'CANCEL_UNCONFIRMED', '팔 정지 확인 없음'
        try:
            while True:
                with self.condition:
                    now, state = time.monotonic(), job['state']
                    counts = job['counts']
                    # 시뮬에서 명시적으로 정지 실패를 확정하면 즉시 상위도 차단합니다.
                    if state is not None and state['status'] != 'RUNNING':
                        if not state['safe_stopped']:
                            error_message = state['error_message'] or '시뮬에서 팔 정지를 확인하지 못했습니다.'
                            self._blocked = True
                        else:
                            code, error_code, error_message = (state[k] for k in ('status', 'error_code', 'error_message'))
                            if job['protocol_error']:
                                code, error_code, error_message = 'FAILED', 'ARM_PROTOCOL_ERROR', job['protocol_error']
                            elif cause and cause != 'CANCELED':
                                code, error_code, error_message = 'FAILED', cause, detail
                            elif code == 'CANCELED' and not handle.is_cancel_requested:
                                code, error_code = 'FAILED', cause or 'ARM_CANCELED'
                        self._completed[(job['session'], job['job_id'])] = dict(job)
                        if len(self._completed) > 32:
                            self._completed.pop(next(iter(self._completed)))
                        terminal = True
                    else:
                        terminal = False
                        if cancel_started is None:
                            if handle.is_cancel_requested:
                                cause, detail = 'CANCELED', '상위 작업 취소 요청'
                            elif self._stopping:
                                cause, detail = 'SHUTDOWN', 'ROS 어댑터 종료'
                            elif job['protocol_error']:
                                cause, detail = 'ARM_PROTOCOL_ERROR', job['protocol_error']
                            elif self.node.session != job['session'] or not self._live(now):
                                cause, detail = 'ARM_LINK_LOST', '시뮬 세션 변경 또는 통신 중단'
                            elif now-job['last_seen'] > self.settings.status_timeout_s:
                                cause, detail = 'ARM_STATUS_TIMEOUT', '팔 상태 수신 시간 초과'
                            elif now-began > self.settings.execution_timeout_s:
                                cause, detail = 'ARM_EXECUTION_TIMEOUT', '팔 실행 wall 시간 초과'
                            if cause:
                                cancel_started, next_send = now, 0.
                        if cancel_started is not None and now-cancel_started >= self.settings.cancel_timeout_s:
                            self._blocked = True
                            error_message = detail+'; 취소 후 팔 정지 결과 수신 실패'
                            terminal = True
                if counts != published:
                    self._feedback(handle, counts)
                    published = counts
                if terminal:
                    if state is not None and state['status'] != 'RUNNING':
                        self._send(job, 'ack')
                    break
                if now >= next_send:
                    operation = 'cancel' if cancel_started is not None else ('start' if state is None else 'keepalive')
                    self._send(job, operation)
                    next_send = now+(self.settings.start_retry_s if operation == 'start' else 1/self.settings.keepalive_hz)
                with self.condition:
                    self.condition.wait(timeout=min(.05, max(.001, next_send-time.monotonic())))
        except Exception as error:
            # 전송·ROS 예외 시 정지를 추정하지 않습니다. lease 만료도 정지 확인을 대체하지 않습니다.
            with self.condition:
                self._blocked = True
            code, error_code = 'FAILED', 'CANCEL_UNCONFIRMED'
            error_message = '팔 연결 예외; 정지 미확인: '+str(error)
            try:
                self._send(job, 'cancel')
            except Exception:
                pass
        finally:
            with self.condition:
                self._active, self._busy = None, False
                self.condition.notify_all()
        result = self.action_type.Result()
        task = handle.request.harvest_task
        result.robot_id, result.task_id, result.window_id = handle.request.robot_id, task.task_id, task.window_id
        result.expected_count = task.expected_count
        result.harvested_count, result.failed_count = job['counts']
        result.result_code, result.error_code, result.error_message = code, error_code or 'NONE', error_message
        result.timestamp = _timestamp()
        if code == 'SUCCESS':
            handle.succeed()
        elif code == 'CANCELED':
            handle.canceled()
        else:
            handle.abort()
        return result

    def request_stop(self) -> None:
        with self.condition:
            self._stopping = True
            self.condition.notify_all()

    def close(self) -> None:
        self.request_stop()
        self.server.destroy()
