"""장치가 발행한 odom을 읽습니다. 바퀴 odom을 다시 계산하지 않습니다."""
from farm_navigation.operation_clock import operation_time
from collections.abc import Callable
import math
import threading
import time
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.callback_groups import CallbackGroup
from .navigation_types import NavigationSettings


class MotionMonitor:
    def __init__(self, node: Node, settings: NavigationSettings, group: CallbackGroup) -> None:
        self._node: Node = node
        self._settings: NavigationSettings = settings
        self._lock = threading.Lock()
        self._message: Odometry | None = None
        self._stationary_epoch = 0
        self._received: float = 0.
        self._subscription = node.create_subscription(Odometry,settings.odom_topic,self._on_odom,10,callback_group=group)

    def _on_odom(self, message: Odometry) -> None:
        with self._lock:
            now = time.monotonic()
            v = message.twist.twist
            values = (v.linear.x, v.linear.y, v.angular.z)
            stopped = (all(map(math.isfinite, values)) and
                       math.hypot(*values[:2]) < self._settings.stopped_linear_mps and
                       abs(values[2]) < self._settings.stopped_angular_rps)
            if not stopped or now-self._received > self._settings.odom_max_age_s:
                self._stationary_epoch += 1
            self._message=message
            self._received=operation_time(self._node)

    def _sample(self) -> tuple[int,bool] | None:
        with self._lock:
            msg=self._message
            age=operation_time(self._node)-self._received
        if msg is None or not 0<=age<=self._settings.odom_max_age_s:
            return None
        twist=msg.twist.twist
        values=(twist.linear.x,twist.linear.y,twist.angular.z)
        if not all(map(math.isfinite,values)): return None
        stopped=(math.hypot(*values[:2])<self._settings.stopped_linear_mps and abs(values[2])<self._settings.stopped_angular_rps)
        return msg.header.stamp.sec*10**9+msg.header.stamp.nanosec,stopped

    def stationary_epoch(self) -> int | None:
        """이동 또는 수신 단절을 넘겨 관측 자세를 재사용하지 않도록 구간을 구분한다."""
        with self._lock:
            epoch = self._stationary_epoch
        return epoch if self.stationary_now() else None

    def stationary_now(self) -> bool:
        sample=self._sample()
        return sample is not None and sample[1]

    def wait_stopped(self, check: Callable[[],None]) -> int:
        """동일한 odom의 반복 수신이나 멈춘 /clock으로 정지 시간이 누적되지 않습니다."""
        deadline=operation_time(self._node)+self._settings.settle_timeout_s
        first: int | None = None
        previous: int | None = None
        while operation_time(self._node)<deadline:
            check()
            sample=self._sample()
            if sample is None:
                first=None
            else:
                stamp,stopped=sample
                if previous is not None and stamp<previous:
                    raise RuntimeError('odom 시각이 역행했습니다.')
                previous=stamp
                if stopped:
                    if first is None: first=stamp
                    if stamp-first>=int(self._settings.settle_s*1e9): return stamp
                else: first=None
            time.sleep(.02)
        raise RuntimeError('정지 확인 실패: 속도·odom 최신성·시각 진행을 확인하세요.')

    def close(self) -> None:
        self._node.destroy_subscription(self._subscription)
