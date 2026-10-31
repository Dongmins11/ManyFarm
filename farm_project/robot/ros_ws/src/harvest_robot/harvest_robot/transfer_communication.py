"""harvest_motion_server 안의 DockTransfer 서버 및 TransferEvent 서비스.

기존 HarvestTask와 node.lock/busy를 공유한다. 로봇 간 직접 통신은 하지 않는다.
인계 기록은 원자적으로 보관하며 중단·미확인 인계는 재시작해도 자동 해제하지 않는다.
"""
from farm_navigation.operation_clock import operation_time
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from rclpy.action import ActionServer, GoalResponse, CancelResponse
from farm_interfaces.action import DockTransfer
from farm_interfaces.srv import TransferEvent
from std_msgs.msg import Int32

from .transfer_devices import TriggerTransferDevices
from .discharge_client import DischargeClient, discharge_parameters
from .discharge_devices import DischargeDevices
from .transfer_rotation import (RotationSettings, RotatingTransferDevices,
                                ROTATION_DEVICE_OPERATIONS, rotation_parameters)
from .transfer_mission import TransferMission, TransferOutcome


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_id(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 128 and all(
        c.isprintable() and not c.isspace() for c in value)


def valid_time(value: Any) -> bool:
    try:
        return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() is not None
    except (ValueError, TypeError):
        return False


class TransferCommunication:
    """node.py에서 한 번 생성한다. 미설정 실물 장치는 구동하지 않는다."""

    def __init__(self, node: Any, navigation_settings: Any = None) -> None:
        self.node = node
        self.active = None
        self.error = ''
        self.loaded_count = None
        self.transfer_required = False
        self._reserved = None
        self._finishing = False
        self._cancel_requested = False
        self._subscription = None

        config = node.config.get("transfer", {})

        def parameter(name: str, default: Any) -> Any:
            node.declare_parameter(name, default)
            return node.get_parameter(name).value

        self.stage_timeout_s = float(parameter('transfer_stage_timeout_s', config.get('stage_timeout_s', 120.0)))
        self.stop_timeout_s = float(parameter('transfer_stop_timeout_s', config.get('stop_timeout_s', 10.0)))
        if any(not math.isfinite(v) or v <= 0 for v in (self.stage_timeout_s, self.stop_timeout_s)):
            raise ValueError('인계 제한 시간은 유한한 양수여야 합니다.')
        self.capacity = parameter('transfer_capacity_count', config.get('capacity_count', 0))
        if type(self.capacity) is not int or self.capacity < 0:
            raise ValueError('transfer_capacity_count는 0 이상의 정수여야 합니다.')
        self.load_topic = parameter('transfer_loaded_count_topic', config.get('loaded_count_topic', ''))
        self.load_source = parameter('transfer_load_source', config.get('load_source', 'external_topic'))
        self.request_count = parameter('transfer_request_count', config.get('request_count', 0))
        if self.load_source not in ('external_topic', 'arm_feedback'):
            raise ValueError('알 수 없는 적재량 입력 방식')
        if type(self.request_count) is not int or not 0 <= self.request_count <= 2147483647:
            raise ValueError('transfer_request_count는 0 이상의 int32여야 합니다.')
        if self.load_source == 'arm_feedback':
            if self.load_topic:
                raise ValueError('팔 누적과 외부 적재 Topic은 동시에 선택할 수 없습니다.')
            self.loaded_count = node.harvest_load.loaded_count
        if not isinstance(self.load_topic, str) or (self.load_topic and (
                not self.load_topic.startswith('/') or self.load_topic == '/'
                or any(c.isspace() for c in self.load_topic))):
            raise ValueError('적재 개수 토픽은 절대 ROS 이름이어야 합니다.')
        services = json.loads(parameter('transfer_device_services', json.dumps(config.get('device_services', {}))))
        mode = parameter('transfer_rotation_mode', config.get('rotation_mode', 'device_services'))
        rotation = json.loads(parameter('transfer_rotation', json.dumps(config.get('rotation', {}))))
        rotation_parameters({'rotation_mode': mode, 'rotation': rotation})
        discharge_mode = parameter('transfer_discharge_mode', config.get('discharge_mode', 'device_services'))
        discharge = json.loads(parameter('transfer_discharge_action', json.dumps(config.get('discharge_action', {}))))
        discharge_parameters({'discharge_mode': discharge_mode, 'discharge_action': discharge,
                              'rotation_mode': mode})
        self._discharge_devices = None
        if mode == 'components':
            from .handoff_devices import ComponentTransferDevices
            runtime = getattr(node, 'handoff_runtime', None)
            if runtime is None:
                raise ValueError('차체 컴포넌트 실행 환경 미구성')
            if discharge_mode == 'action':
                auxiliary = TriggerTransferDevices(node, services, operations=('prepare_arm', 'stop'))
                client = DischargeClient(node, **discharge, group=node.callbacks)
                devices = self._discharge_devices = DischargeDevices(auxiliary, client)
            else:
                devices = TriggerTransferDevices(node, services, operations=ROTATION_DEVICE_OPERATIONS)
            self.devices = ComponentTransferDevices(devices, runtime.build_body, runtime.ready,
                self.stage_timeout_s, self.stop_timeout_s, clock_factory=runtime.pause_clock.scoped, clock=lambda: operation_time(node))
        elif mode == 'nav2_spin':
            if navigation_settings is None:
                raise ValueError('공통 회전에는 기존 주행 설정과 위치/정지 관측 연결이 필요합니다.')
            from farm_navigation.spin_client import SpinClient
            rotation_settings = RotationSettings.from_mapping(rotation)
            if discharge_mode == 'action':
                auxiliary = TriggerTransferDevices(node, services, operations=('prepare_arm', 'stop'))
                client = DischargeClient(node, **discharge, group=node.callbacks)
                devices = self._discharge_devices = DischargeDevices(auxiliary, client)
            else:
                devices = TriggerTransferDevices(node, services, operations=ROTATION_DEVICE_OPERATIONS)
            spin = SpinClient(node, rotation_settings.endpoint, navigation_settings, node.callbacks)
            self.devices = RotatingTransferDevices(devices, spin, node.poses, node.motion,
                rotation_settings, self.stage_timeout_s, self.stop_timeout_s, clock=lambda: operation_time(node))
        else:
            self.devices = TriggerTransferDevices(node, services)
        journal = parameter('transfer_journal_path', config.get('journal_path', str(Path.home() / '.local/state/manyfarm'
                             / node.config['robot_id'] / 'transfer.json')))
        if not isinstance(journal, str) or not journal.strip():
            raise ValueError('인계 기록 경로가 비어 있습니다.')
        self.path = Path(journal).expanduser()
        self.records = self._load()
        if any(r.get('recovery_required') or r.get('active') for r in self.records.values()):
            node.blocked = True
            self.error = 'TRANSFER_RECOVERY_REQUIRED'
        if self.load_topic:
            self._subscription = node.create_subscription(Int32, self.load_topic,
                lambda msg: self.update_loaded_count(msg.data), 10, callback_group=node.callbacks)
        self.server = ActionServer(node, DockTransfer, 'dock_transfer',
            execute_callback=self.execute, goal_callback=self.accept,
            cancel_callback=self.cancel, callback_group=node.callbacks)
        self.service = node.create_service(TransferEvent, 'transfer_event', self.receive,
                                           callback_group=node.callbacks)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (data.get('version') != 1 or data.get('robot_id') != self.node.config['robot_id']
                or not isinstance(data.get('records'), dict)):
            raise ValueError('인계 기록 형식/로봇 ID 불일치. 기록을 임의 삭제하지 마세요.')
        for key, value in data['records'].items():
            if (not valid_id(key) or not isinstance(value, dict)
                    or not valid_id(value.get('transfer_id'))
                    or type(value.get('active')) is not bool
                    or type(value.get('recovery_required')) is not bool):
                raise ValueError('인계 기록 손상. 현장 상태 확인이 필요합니다.')
        return data['records']

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.transfer-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'version': 1, 'robot_id': self.node.config['robot_id'],
                           'records': self.records}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def update_loaded_count(self, count: int) -> None:
        """장치가 확인한 현재 적재 개수. 예상 개수/수확 Goal로 증가시키지 않는다."""
        if type(count) is not int or not 0 <= count <= 2147483647:
            self.node.get_logger().warning('잘못된 적재 개수 입력 무시')
            return
        with self.node.lock:
            if self.load_source != 'external_topic':
                return
            # 인계 중 배출 해소 판정은 discharge 완료 응답 하나를 기준으로 한다.
            # 늦게 도착한 양수 적재 샘플이 진행 중 완료를 덮어쓰지 않도록 한다.
            if self._reserved is not None or self.active is not None:
                return
            self._set_loaded_count(count)
            # 센서 한 번의 0이나 임계치 하락으로 선호출 요청을 해제하지 않는다.

    def _set_loaded_count(self, count: int) -> None:
        """node.lock 안에서 호출한다. 0 기준은 기존 용량 80% 정책을 사용한다."""
        self.loaded_count = count
        threshold = self.request_count or (math.ceil(self.capacity * 0.8) if self.capacity else 0)
        if threshold and count >= threshold:
            self.transfer_required = True

    def update_harvest_load(self) -> None:
        """공통 팔 수량을 읽어 호출 상태에 연결한다. 수확 실행은 중단하지 않는다."""
        with self.node.lock:
            if self.load_source == 'arm_feedback' and self._reserved is None and self.active is None:
                self._set_loaded_count(self.node.harvest_load.loaded_count)

    def snapshot(self) -> dict:
        with self.node.lock:
            active = self.active
            return {'task_id': self._reserved[0] if self._reserved else '',
                    'phase': active[1].phase if active else
                             'TRANSFER_PREPARING' if self._reserved else '',
                    'loaded_count': self.loaded_count,
                    'transfer_required': self.transfer_required,
                    'error': self.error}

    def accept(self, goal: Any) -> Any:
        if getattr(self.node, 'body_trial', None) is not None:
            return GoalResponse.REJECT  # 시험 모드에서는 운영 인계 요청을 받지 않는다.
        valid = (goal.robot_id == self.node.config['robot_id']
                 and all(valid_id(v) for v in (goal.task_id, goal.transfer_id, goal.transport_robot_id))
                 and goal.transport_robot_id != goal.robot_id
                 and type(goal.expected_count) is int and 0 <= goal.expected_count <= 2147483647
                 and valid_time(goal.timestamp))
        if not valid or not self.devices.ready():
            self.node.get_logger().warning('DockTransfer 거절: Goal 형식 또는 장치 연결 확인 필요')
            return GoalResponse.REJECT
        with self.node.lock:
            if (self.node.busy or self.node.blocked or self.node.stopping
                    or goal.task_id in self.node.completed_ids or goal.task_id in self.records
                    or any(r['transfer_id'] == goal.transfer_id for r in self.records.values())
                    or len(self.records) >= 10000):
                return GoalResponse.REJECT
            # 수확/복귀를 선점하지 않으며 인계 중에는 어느 이동도 선점할 수 없다.
            if not self.node.handoff.reserve('transfer', goal.task_id,
                                             preempt=False, interruptible=False):
                return GoalResponse.REJECT
            self.records[goal.task_id] = {'transfer_id': goal.transfer_id,
                'active': True, 'recovery_required': True, 'started_at': timestamp()}
            try:
                self._save()
            except Exception as error:
                self.node.blocked = True
                self.error = 'TRANSFER_JOURNAL_ERROR'
                self.node.handoff.release('transfer', goal.task_id)
                self.node.get_logger().error(str(error))
                return GoalResponse.REJECT
            self.node.busy = True
            self._cancel_requested = False
            self._reserved = (goal.task_id, goal.transfer_id)
        return GoalResponse.ACCEPT

    def receive(self, request: Any, response: Any) -> Any:
        with self.node.lock:
            active = self.active
            if active is None:
                reply = (False, 'NO_ACTIVE_TRANSFER', '실행 중인 인계가 없습니다.')
            else:
                handle, mission = active
                goal = handle.request
                expected = (goal.robot_id, goal.task_id, goal.transfer_id, goal.transport_robot_id)
                actual = (request.robot_id, request.task_id, request.transfer_id, request.source_robot_id)
                if actual != expected:
                    reply = (False, 'TRANSFER_ID_MISMATCH', '인계 작업 또는 상대 로봇 ID 불일치')
                elif not valid_time(request.timestamp):
                    reply = (False, 'INVALID_TIMESTAMP', '시간대 포함 ISO 8601 시각이 필요합니다.')
                elif self._cancel_requested or handle.is_cancel_requested or self.node.stopping:
                    reply = (False, 'TRANSFER_STOPPING', '취소/종료 중입니다.')
                else:
                    reply = mission.receive(request.event)
            response.accepted, response.error_code, response.error_message = reply
            response.timestamp = timestamp()
        return response

    def cancel(self, handle: Any) -> Any:
        """종료 확정과 취소 수락을 같은 잠금으로 직렬화한다."""
        with self.node.lock:
            if self._finishing or self._reserved != (handle.request.task_id, handle.request.transfer_id):
                return CancelResponse.REJECT
            self._cancel_requested = True
            return CancelResponse.ACCEPT

    def _feedback(self, handle: Any, event: str) -> None:
        message = DockTransfer.Feedback()
        for name in ('robot_id', 'task_id', 'transfer_id'):
            setattr(message, name, getattr(handle.request, name))
        message.event, message.timestamp = event, timestamp()
        handle.publish_feedback(message)

    def execute(self, handle: Any) -> Any:
        """장치 정리와 상태 확정을 마친 뒤에만 공통 실행 소유권을 반납한다."""
        task_id = handle.request.task_id
        try:
            # 예약은 유휴에서만 가능하다. 취소 처리는 기존 미션에서 결과로 반환한다.
            self.node.handoff.acquire('transfer', task_id, lambda: None)
            return self._execute_transfer(handle)
        except Exception:
            # 예기치 않은 통신 예외도 자동으로 주행 허가로 바꾸지 않는다.
            with self.node.lock:
                self.node.blocked = True
                self.error = 'TRANSFER_INTERNAL_ERROR'
                self.node.busy = False
            raise
        finally:
            self.node.handoff.release('transfer', task_id)

    def _execute_transfer(self, handle: Any) -> Any:
        goal = handle.request
        mission = TransferMission(self.devices, lambda event: self._feedback(handle, event),
            lambda: self._cancel_requested or handle.is_cancel_requested, lambda: self.node.stopping,
            self.stage_timeout_s, self.stop_timeout_s, clock=lambda: operation_time(self.node), event_timeout_s=None)
        with self.node.lock:
            self.active = (handle, mission)
        if self._discharge_devices is not None:
            self._discharge_devices.begin(goal.transfer_id)
        outcome = mission.run()
        with self.node.lock:
            self._finishing = True
            if outcome.result_code == 'SUCCESS' and (self._cancel_requested or handle.is_cancel_requested):
                outcome = replace(outcome, result_code='CANCELED', error_code='CANCELED',
                                  error_message='복구 완료 직후 취소 요청 수락')
            if outcome.transfer_complete and outcome.restore_complete and not outcome.recovery_required:
                if self.load_source == 'arm_feedback':
                    self.node.harvest_load.reset_after_transfer()
                self.loaded_count = 0
                self.transfer_required = False
            if outcome.result_code == 'SUCCESS':
                self.node.completed_ids.add(goal.task_id)
            if outcome.recovery_required:
                self.node.blocked = True
                self.error = outcome.error_code
            self.records[goal.task_id].update(active=False,
                recovery_required=outcome.recovery_required,
                result_code=outcome.result_code, finished_at=timestamp())
            try:
                self._save()
            except Exception as error:
                self.node.blocked = True
                self.error = 'TRANSFER_JOURNAL_ERROR'
                outcome = replace(outcome, result_code='FAILED', error_code=self.error,
                                  error_message=str(error), recovery_required=True)
                self.records[goal.task_id].update(recovery_required=True, result_code='FAILED')
                try:
                    self._save()
                except Exception:
                    self.node.get_logger().error('인계 기록 저장 불가: 재시작 전 현장 상태와 기록 확인 필요')
        if outcome.result_code == 'CANCELED':
            # rclpy는 cancel_callback 반환 뒤 Goal 상태를 CANCELING으로 바꾼다.
            # 내부 취소 플래그만 보고 canceled()를 너무 일찍 부르지 않는다.
            deadline = operation_time(self.node) + self.stop_timeout_s
            while not handle.is_cancel_requested and operation_time(self.node) < deadline:
                time.sleep(0.01)
            if not handle.is_cancel_requested:
                outcome = replace(outcome, result_code='FAILED', error_code='CANCEL_STATE_UNCONFIRMED',
                                  error_message='ROS 취소 상태 전환 미확인', recovery_required=True)
                with self.node.lock:
                    self.node.blocked = True
                    self.error = outcome.error_code
                    self.records[goal.task_id].update(recovery_required=True, result_code='FAILED')
                    try:
                        self._save()
                    except Exception as error:
                        self.node.get_logger().error('취소 상태 기록 실패: ' + str(error))
        result = DockTransfer.Result()
        for name in ('robot_id', 'task_id', 'transfer_id', 'expected_count'):
            setattr(result, name, getattr(goal, name))
        for name in ('result_code', 'error_code', 'error_message', 'transfer_complete',
                     'transport_clear', 'restore_complete'):
            setattr(result, name, getattr(outcome, name))
        result.timestamp = timestamp()
        try:
            if outcome.result_code == 'SUCCESS':
                handle.succeed()
            elif outcome.result_code == 'CANCELED':
                handle.canceled()
            else:
                handle.abort()
        finally:
            with self.node.lock:
                self.active = None
                self._reserved = None
                self._finishing = False
                self.node.busy = False
        return result

    def close(self) -> None:
        self.server.destroy()
        self.node.destroy_service(self.service)
        if self._subscription is not None:
            self.node.destroy_subscription(self._subscription)
        self.devices.close(self.node)
