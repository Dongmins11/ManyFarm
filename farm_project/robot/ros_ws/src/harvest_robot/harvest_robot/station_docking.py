"""실물 스테이션 도킹 조립. 벽 관측·Nav2·출력 소유권을 연결하고 직접 제어하지 않는다."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import queue
import threading
import time
import uuid
from typing import Any, Callable

from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float64MultiArray
from rclpy.qos import qos_profile_sensor_data
from farm_navigation.configuration import read_mapping, resolve_file
from farm_navigation.wall_observation import DockWallTracker
from farm_navigation.wall_trial_support import isolated_parameters
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.navigator import Navigator
from .handoff_server_config import flatten
from .pause_clock import PauseClock


def load_config(root: Path, path: str) -> dict:
    """측정값과 선택 설정을 읽는다. 허용치 미확정 상태에서는 선택 실행하지 않는다."""
    config = read_mapping(resolve_file(root, path))
    base = read_mapping(resolve_file(root, config['controller_defaults']))
    controller = dict(base['controller'], **config['controller'])
    # 미확정 값을 기존 인계 허용치로 채우지 않는다. 확정된 값만 적용한다.
    for key in ('distance_tolerance', 'lateral_tolerance', 'angle_tolerance'):
        v = controller.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError('스테이션 도킹 허용치 미확정: ' + key)
    if controller.get('station_docking') is not True:
        raise ValueError('스테이션 도킹 모드 설정이 필요합니다.')
    return dict(config, controller=controller)


def server_config(nav: dict, robot_id: str, config: dict) -> dict:
    """기존 costmap을 복사해 실물 전용 namespace의 벽 제어 서버를 구성한다."""
    prefix = '/' + robot_id + '/station_docking'
    cp = flatten(nav['controller_server']['ros__parameters'])
    cm = flatten(nav['local_costmap']['local_costmap']['ros__parameters'])
    values = isolated_parameters(cp, cm, prefix, '/'+robot_id+'/scan_filtered',
                                 '/'+robot_id+'/odom', config)
    server = values[prefix+'/controller_server']['ros__parameters']
    server['wall_progress.plugin'] = 'farm_wall_controller::WaitingProgressChecker'
    return values


def target_error(target: dict, pose: Any, limits: dict) -> dict:
    """목표 자세 축의 앞뒤·좌우 오차(m)와 방향 오차(rad)를 계산한다."""
    dx, dy = target['x']-pose[0, 3], target['y']-pose[1, 3]
    yaw = target['yaw']
    x = math.cos(yaw)*dx + math.sin(yaw)*dy
    y = -math.sin(yaw)*dx + math.cos(yaw)*dy
    a = math.remainder(yaw-math.atan2(pose[1, 0], pose[0, 0]), math.tau)
    return dict(longitudinal_error_m=x, lateral_error_m=y, heading_error_rad=a,
                accepted=abs(x)<=limits['distance_tolerance'] and
                abs(y)<=limits['lateral_tolerance'] and abs(a)<=limits['angle_tolerance'])


class StationDocking:
    """한 복귀 Action 안에서 벽 목표를 갱신하고 FollowPath 실행·정지 확인을 재사용한다."""

    def __init__(self, node: Any, *, config: dict, settings: Any, robot_id: str,
                 poses: Any, motion: Any, callbacks: Any, check: Callable[[], None],
                 owns_output: Callable[[], bool]) -> None:
        if config['reference']['frame_id'] != settings.base_frame:
            raise ValueError('도킹 측정 기준 frame과 차체 frame 불일치')
        self._node, self._config, self._poses = node, config, poses
        self._check, self._owns_output = check, owns_output
        self._lock = threading.RLock()
        self._enabled = False
        self._latest: dict | None = None
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._error = ''
        prefix = '/' + robot_id + '/station_docking'
        c = config['controller']
        self._pause_clock = PauseClock(unlimited=bool(c.get('wait_until_fresh', False)))
        self._controller_wait = (0., False)
        self._last_command = (0., False)
        self._pause_session = uuid.uuid4().int & ((1 << 48)-1)
        self._pause_sequence = 0
        self._wait_topic = prefix+'/controller_wait'
        self._settings = replace(settings, mode='follow_path', parallel_approach=False,
            map_frame='odom', follow_action=prefix+'/follow_path', controller_node=prefix+'/controller_server',
            controller_id='WallAlign', goal_checker_id='wall_goal', progress_checker_id='wall_progress',
            tf_recovery_enabled=False, collision_retry_count=0,
            arrival_tolerance_m=c['distance_tolerance'], heading_tolerance_rad=c['angle_tolerance'])
        self._output = node.create_publisher(Twist, 'cmd_vel_normal', 10)
        self._target_publisher = node.create_publisher(PoseStamped, prefix+'/dock_target', 1)
        self._pause_publisher = node.create_publisher(Float64MultiArray, prefix+'/handoff_wait_clock', 1)
        self._subscriptions = [
            node.create_subscription(Bool, self._wait_topic, self._receive_wait, 1, callback_group=callbacks),
            node.create_subscription(LaserScan, 'scan_filtered', self._scan, qos_profile_sensor_data,
                                     callback_group=callbacks),
            node.create_subscription(Twist, prefix+'/raw_nav', self._relay, 10, callback_group=callbacks)]
        self._client = Nav2Client(node, self._settings, callbacks, execution_clock=self._pause_clock.scoped)
        self._navigator = Navigator(node, self._settings, self._client, poses, motion, check,
            explicit_routes=True, stop_output=self._disable, arrival_validator=self._validate)
        self._pause_timer = node.create_timer(.05, self._publish_pause_clock, callback_group=callbacks)

    def _receive_wait(self, msg: Bool) -> None:
        """기존 벽 제어기의 관측 대기 상태와 수신 시각을 보관한다."""
        with self._lock:
            self._controller_wait = (time.monotonic(), bool(msg.data))

    def _publish_pause_clock(self) -> None:
        """이미 0출력으로 관측을 기다린 시간만 기존 실행·진행 시계에 전달한다."""
        with self._lock:
            now = time.monotonic()
            recent, waiting = self._controller_wait
            command_time, zero = self._last_command
            active = (self._enabled and self._owns_output() and waiting and zero
                and now-recent <= .2 and now-command_time <= .2
                and len(self._node.get_publishers_info_by_topic(self._wait_topic)) == 1)
            total = self._pause_clock.update(bool(active))
            self._pause_sequence += 1
            self._pause_publisher.publish(Float64MultiArray(data=[float(self._pause_session),
                float(self._pause_sequence), total, self._node.get_clock().now().nanoseconds/1e9]))

    def _scan(self, scan: LaserScan) -> None:
        """최신 scan 하나만 처리 대기시켜 ROS 콜백을 막지 않는다."""
        with self._lock:
            if self._worker is None:
                return
        try:
            self._queue.put_nowait(scan)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(scan)
            except queue.Full:
                pass

    def _relay(self, command: Twist) -> None:
        """복귀 제어권을 소유한 동안만 기존 출력 경로로 전달한다."""
        with self._lock:
            if self._enabled and self._owns_output():
                self._output.publish(command)
                self._last_command = (time.monotonic(),
                    command.linear.x == 0. and command.linear.y == 0. and command.angular.z == 0.)

    def _disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._pause_clock.update(False)
            self._controller_wait = (0., False)
            self._last_command = (0., False)
            if self._owns_output():
                self._output.publish(Twist())

    def _observe(self) -> None:
        tracker = DockWallTracker(self._config)
        while not self._stop.is_set():
            try:
                scan = self._queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                stamp = scan.header.stamp.sec*10**9 + scan.header.stamp.nanosec
                age = (self._node.get_clock().now().nanoseconds-stamp)/1e9
                if not 0 <= age <= self._config['controller']['observation_age']:
                    continue
                def check() -> None:
                    if self._stop.is_set():
                        raise RuntimeError('도킹 관측 종료')
                    self._check()
                    if (self._node.get_clock().now().nanoseconds-stamp)/1e9 > self._config['controller']['observation_age']:
                        raise RuntimeError('도킹 관측 시각 만료: 최신 scan 대기')
                processing_started = time.monotonic()
                record = dict(stamp_ns=stamp,
                    scan={k: getattr(scan, k) for k in ('ranges', 'angle_min', 'angle_increment', 'range_min', 'range_max')},
                    base_from_scan=self._poses.lookup(self._settings.base_frame, scan.header.frame_id, stamp, check),
                    odom_from_base=self._poses.lookup('odom', self._settings.base_frame, stamp, check))
                tf_finished = time.monotonic()
                value = tracker.observe(record)
                value['tf_s'] = tf_finished-processing_started
                value['fit_s'] = time.monotonic()-tf_finished
                value['processing_s'] = time.monotonic()-processing_started
                value['publish_age_s'] = (self._node.get_clock().now().nanoseconds-stamp)/1e9
                if value['publish_age_s'] > self._config['controller']['observation_age']:
                    continue
                if not value['ready']:
                    continue
                msg = PoseStamped()
                msg.header.frame_id, msg.header.stamp = 'odom', scan.header.stamp
                msg.pose.position.x, msg.pose.position.y = value['x'], value['y']
                msg.pose.orientation.z, msg.pose.orientation.w = math.sin(value['yaw']/2), math.cos(value['yaw']/2)
                with self._lock:
                    self._latest = value
                    self._error = ''
                self._target_publisher.publish(msg)
            except Exception as error:
                # 이전 시각을 바꾸지 않는다. Nav2의 기존 관측 만료 처리가 정지를 담당한다.
                with self._lock:
                    self._error = str(error)

    def _target(self, check: Callable[[], None]) -> dict:
        deadline = time.monotonic() + self._settings.readiness_timeout_s
        while True:
            check()
            with self._lock:
                target, error = deepcopy(self._latest), self._error
            if target is not None:
                age = (self._node.get_clock().now().nanoseconds-target['stamp_ns'])/1e9
                if 0 <= age <= self._config['controller']['observation_age']:
                    return target
            if time.monotonic() >= deadline:
                raise RuntimeError('도킹 벽 관측 준비 대기: '+error)
            time.sleep(.02)

    def _validate(self, stamp: int, check: Callable[[], None]) -> dict:
        # 정지 후에도 최신 벽 목표와 동시각 자세로 확인한다. 이전 지도 도착 판정을 쓰지 않는다.
        target = self._target(check)
        pose = self._poses.lookup('odom', self._settings.base_frame, target['stamp_ns'], check)
        value = target_error(target, pose, self._config['controller'])
        self._node.get_logger().info('STATION_DOCKING '+json.dumps(value))
        return value

    def execute(self) -> None:
        self._client.preflight(self._check, wall_parameters=self._config['controller'])
        with self._lock:
            if self._worker is not None:
                raise RuntimeError('도킹 관측이 이미 실행 중입니다.')
            self._latest = None
            self._stop.clear()
            self._worker = threading.Thread(target=self._observe, name='station_dock_observer')
            self._worker.start()
        target = self._target(self._check)
        pose = self._poses.lookup('odom', self._settings.base_frame, target['stamp_ns'], self._check)
        start = (float(pose[0, 3]), float(pose[1, 3]))
        end = (target['x'], target['y'])
        # Path는 기존 FollowPath 호출 계약이다. 실제 목표는 설정에서 선택한 벽 관측으로 계속 갱신한다.
        route = RoutePlan(uuid.uuid4().hex, '', 'odom', (start, end), (), math.dist(start, end),
                          (target['yaw'], target['yaw']))
        with self._lock:
            self._check()
            if not self._owns_output():
                raise RuntimeError('도킹 출력 소유권 상실')
            self._enabled = True
        self._navigator.navigate(end, target['yaw'], route_plan=route)

    def cleanup(self) -> None:
        self._disable()
        try:
            self._navigator.cancel_nav()
        finally:
            self._stop.set()
            worker = self._worker
            if worker is not None:
                worker.join()
            with self._lock:
                self._worker = None
                self._latest = None
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def close(self) -> None:
        self.cleanup()
        self._client.close()
        self._node.destroy_timer(self._pause_timer)
        for subscription in self._subscriptions:
            self._node.destroy_subscription(subscription)
        self._node.destroy_publisher(self._target_publisher)
        self._node.destroy_publisher(self._pause_publisher)
        self._node.destroy_publisher(self._output)
