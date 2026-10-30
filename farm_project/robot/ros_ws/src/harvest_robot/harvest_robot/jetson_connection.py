"""Pinky의 선택형 Jetson 상태 연결. 서버·브리지·복구 요청은 자동 실행하지 않는다.

별도 상호배제 콜백 그룹에서 입력을 받고 짧은 캐시 판정만 발행한다.
수신 상태는 팔 Goal 직전 준비 확인에만 사용하며 주행·인계·실행 중 중단 판단에 연결하지 않는다.
"""
from collections.abc import Callable
from dataclasses import fields
import threading
import time
from typing import Any
import uuid

from .jetson_state import JetsonSettings, RuntimeSample, RuntimeTracker, ControlTracker


def create_jetson_connection(node: Any, navigation: Any) -> 'JetsonConnection | None':
    """설정이 없으면 ROS 확장 타입을 import하거나 통신 객체를 생성하지 않는다."""
    settings = JetsonSettings.from_config(node.config.get('jetson_connection', {}))
    if settings is None:
        return None
    return JetsonConnection(node, navigation, settings)


class JetsonConnection:
    def __init__(self, node: Any, navigation: Any, settings: JetsonSettings) -> None:
        from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
        from rclpy.clock import Clock, ClockType
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
        from std_msgs.msg import Bool
        from std_srvs.srv import SetBool
        from nav_msgs.msg import Odometry
        from jetson_harvest_interfaces.msg import ControlState, RuntimeStatus

        # V3와 구형 설치본이 섞이면 발행 전에 계약 불일치를 알린다.
        expected_fields = {'stamp': 'builtin_interfaces/Time', 'robot_id': 'string',
            'boot_id': 'string', 'sequence': 'uint64', 'base_stopped': 'boolean',
            'transfer_active': 'boolean'}
        if ControlState.get_fields_and_field_types() != expected_fields:
            raise RuntimeError('CONTROL_STATE_SCHEMA_MISMATCH: jetson_harvest_interfaces 3.0.0 재빌드/source 필요')

        self._node, self._navigation, self._settings = node, navigation, settings
        self._lock = threading.RLock()
        self._boot_id, self._sequence = uuid.uuid4().hex, 0
        self._group = MutuallyExclusiveCallbackGroup()
        self._message_type = ControlState
        self._test_enabled = False
        self._test_message_type = Bool
        self._runtime = RuntimeTracker(node.config['robot_id'], settings)
        self._control = ControlTracker(odom_age_s=navigation.odom_max_age_s,
            settle_s=navigation.settle_s, linear_mps=navigation.stopped_linear_mps,
            angular_rps=navigation.stopped_angular_rps,
            future_s=settings.future_tolerance_s)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self._publisher = node.create_publisher(ControlState, settings.control_state_topic, qos)
        self._subscriptions = [
            node.create_subscription(RuntimeStatus, settings.runtime_status_topic, self._receive_runtime,
                                     qos, callback_group=self._group),
            node.create_subscription(Odometry, navigation.odom_topic, self._receive_odom,
                                     qos_profile_sensor_data, callback_group=self._group)]
        # Pinky 로컬 시험 제어다. Jetson/관제 브리지에 별도 발행기를 추가하지 않는다.
        test_prefix = '/' + node.config['robot_id'] + '/transfer_test_mode'
        self._test_publisher = node.create_publisher(Bool, test_prefix + '/enabled', qos)
        self._test_service = node.create_service(SetBool, test_prefix + '/set_enabled',
            self._set_transfer_test, callback_group=self._group)
        self._clock = Clock(clock_type=ClockType.STEADY_TIME)
        self._timer = node.create_timer(1.0/settings.control_state_rate_hz, self._publish,
                                       callback_group=self._group, clock=self._clock)

    def _now(self) -> tuple[int, float]:
        return self._node.get_clock().now().nanoseconds, time.monotonic()

    @staticmethod
    def _stamp(message: Any) -> int:
        return message.sec*10**9 + message.nanosec

    def _receive_odom(self, message: Any) -> None:
        now_ns, now_s = self._now()
        twist = message.twist.twist
        valid = (message.header.frame_id == self._settings.odom_frame
                 and message.child_frame_id == self._navigation.base_frame)
        with self._lock:
            self._control.odom(self._stamp(message.header.stamp), twist.linear.x, twist.linear.y,
                               twist.angular.z, now_ns, now_s, valid)

    def _receive_runtime(self, message: Any) -> None:
        values = {f.name: getattr(message, f.name) for f in fields(RuntimeSample) if f.name != 'stamp_ns'}
        sample = RuntimeSample(stamp_ns=self._stamp(message.stamp), **values)
        with self._lock:
            self._runtime.receive(sample, time.monotonic())

    def _transfer(self) -> dict:
        transfer = getattr(self._node, 'transfer', None)
        return transfer.snapshot() if transfer is not None else {'task_id': '', 'phase': ''}

    def _motion_idle(self, transfer: dict) -> bool:
        """팔 작업의 busy는 이동으로 취급하지 않는다. 미확정/실행 중 주행은 차단한다."""
        node = self._node
        # blocked는 업무 차단이다. 팔 오류 복구에 필요한 실제 차체 정지를 부정하지 않는다.
        if node.stopping:
            return False
        clients = [getattr(node, name, None) for name in ('client', 'work_client', 'exit_client')]
        runtime = getattr(node, 'handoff_runtime', None)
        if runtime is not None:
            clients.extend(binding.client for binding in runtime.bindings.values())
            clients.append(runtime.spin)
        if any(client is not None and client.has_goal for client in clients):
            return False
        if transfer['task_id']:
            return transfer['phase'] in ('TRANSFER_PREPARING', 'WAIT_DOCK_STABLE',
                                         'TRANSFERRING', 'WAIT_TRANSPORT_CLEAR')
        current = node.handoff.current
        if current is not None:
            return current[0] == 'work' and getattr(node, 'mission_stage', '') == 'ARM'
        return not node.busy

    def _control_values(self, transfer: dict) -> tuple[int, bool] | None:
        idle = self._motion_idle(transfer)
        with self._lock:
            now_ns, now_s = self._now()
            if not self._control.observation_fresh(now_ns, now_s):
                return None
            return self._control.values(now_ns, now_s, motion_idle=idle)

    def _test_available(self, transfer: dict) -> bool:
        """운영 작업이 소유한 상태를 시험값으로 덮어쓰지 않는다. 작업 수락은 변경하지 않는다."""
        return (not transfer['task_id'] and not self._node.busy and not self._node.blocked
                and self._node.handoff.current is None and self._motion_idle(transfer))

    def _set_transfer_test(self, request: Any, response: Any) -> Any:
        """시험 transfer_active만 켜고 끈다. 이동·배출·복구·적재량 변경은 요청하지 않는다."""
        with self._lock:
            if request.data and not self._test_available(self._transfer()):
                response.success = False
                response.message = '운영 주행·수확·인계 작업 중에는 배출 시험 모드를 켤 수 없습니다.'
                return response
            self._test_enabled = bool(request.data)
            response.success = True
            response.message = ('배출 시험 모드 켜짐: transfer_active=true, 정지는 실제 관측값 유지'
                                if self._test_enabled else '배출 시험 모드 꺼짐: 운영 인계 상태로 복귀')
            self._test_publisher.publish(self._test_message_type(data=self._test_enabled))
        return response

    def _publish(self) -> None:
        transfer = self._transfer()
        with self._lock:
            if self._test_enabled and not self._test_available(transfer):
                self._test_enabled = False
                self._node.get_logger().info('운영 작업 시작으로 배출 시험 모드를 해제합니다.')
            test_enabled = self._test_enabled
            self._test_publisher.publish(self._test_message_type(data=test_enabled))
        values = self._control_values(transfer)
        if values is None:
            return
        stamp_ns, stopped = values
        message = self._message_type()
        message.robot_id, message.boot_id = self._node.config['robot_id'], self._boot_id
        self._sequence += 1
        message.sequence = self._sequence
        message.stamp.sec, message.stamp.nanosec = divmod(stamp_ns, 10**9)
        message.base_stopped = stopped
        message.transfer_active = bool(transfer['task_id']) or test_enabled
        self._publisher.publish(message)

    def snapshot(self) -> dict:
        """마지막 Jetson 원문 값과 수신 경과 시간을 조회한다. 작업 상태를 바꾸지 않는다."""
        with self._lock:
            return self._runtime.snapshot(time.monotonic())

    def wait_before_send(self, check: Callable[[], None], timeout_s: float) -> None:
        """팔 Goal 전송 직전만 회신의 준비 상태를 기다린다. 기존 취소 확인은 유지한다."""
        from .arm_client import ArmExecutionError
        deadline = time.monotonic() + timeout_s
        while True:
            check()
            with self._lock:
                if self._runtime.ready_to_send(*self._now()):
                    return
            if time.monotonic() >= deadline:
                raise ArmExecutionError('ARM_UNAVAILABLE', 'Jetson 최신 depth_v11 ready 상태 대기 시간 초과')
            time.sleep(.01)

    def close(self) -> None:
        """자동 stop/recover 호출 없이 이 연결의 ROS 자원만 해제한다."""
        self._node.destroy_timer(self._timer)
        for subscription in self._subscriptions:
            self._node.destroy_subscription(subscription)
        self._node.destroy_publisher(self._publisher)
        self._node.destroy_service(self._test_service)
        self._node.destroy_publisher(self._test_publisher)
