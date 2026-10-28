from .handoff_locking import TimingProbe, TimedRLock
from .transient_gate import TransientCommandGate
from .handoff_wait import InputUnavailable, ClearancePending, WaitingPoses, TransformUnavailable
"""수확 Node의 센서·서버·단일 출력 연결. 명시 선택한 인계 환경에서만 생성한다."""
import math
import secrets
from std_msgs.msg import Bool, Float64MultiArray
from .pause_clock import PauseClock
import threading
import time
from dataclasses import replace
from typing import Any

from geometry_msgs.msg import Twist, PoseStamped, PolygonStamped
from nav_msgs.msg import Odometry
from nav2_msgs.msg import Costmap
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rosidl_runtime_py.convert import message_to_ordereddict
from farm_navigation.configuration import read_mapping, resolve_file, load_nav2_parameters
from farm_navigation.arc_clearance import check_grid, ObstacleBlocked
from farm_navigation.arc_isolation import CommandGate
from farm_navigation.wall_trial_support import WallCommandGate
from farm_navigation.wall_observation import WallTracker
from farm_navigation.transfer_arc import ArcSpec, wrap
from farm_navigation.measured_velocity_guard import MeasuredVelocityGuard, MeasuredVelocityLimits
from farm_navigation.nav2_client import Nav2Client
from farm_navigation.spin_client import SpinClient
from .handoff_entry import WindowEntryReference
from .handoff_window import WindowCommandGate
from .handoff_clearance import AsyncClearance, grid_key
from .handoff_server_config import build_server_config
from .handoff_profile import MotionProfile
from .handoff_navigation import NavigationBinding
from .handoff_planning import HandoffPlanner, CompletionPolicy
from .handoff_vicpinky import build_vicpinky_motion
from .transfer_retreat import alignment_footprint
from .handoff_input_trace import InputTrace, traced


def stamp(message: Any) -> int:
    return message.header.stamp.sec * 10**9 + message.header.stamp.nanosec


class ScanTemporarilyUnavailable(InputUnavailable):
    """벽 관측용 scan 부재/과거 만료만 구분한다. 다른 보호는 유지한다."""


class HandoffRuntime:
    def __init__(self, node: Any, environment: dict, settings: Any) -> None:
        if node.mode not in ('real', 'sim') or settings.tf_recovery_enabled:
            raise ValueError('Twist 단일 출력 및 TF 복구 비활성 환경이 필요합니다.')
        self.node, self.settings = node, settings
        cfg = node.config['handoff_runtime']
        self.wall = read_mapping(resolve_file(node.root, cfg['wall_config']))
        self._sensor_wait_indefinite = cfg.get('sensor_wait_indefinite', False)
        if type(self._sensor_wait_indefinite) is not bool:
            raise ValueError('sensor_wait_indefinite는 bool이어야 합니다.')
        self._recovery_timeout = float(cfg.get('transient_recovery_timeout_s', 5.0))
        if not math.isfinite(self._recovery_timeout) or self._recovery_timeout <= 0:
            raise ValueError('재관측 대기 시간은 유한한 양수 초 필요')
        self.policy = read_mapping(resolve_file(node.root, cfg['monitor_policy']))
        self.spec = ArcSpec(**cfg['arc'])
        self.completion = CompletionPolicy(**cfg.get('completion', {}))
        if (self.completion.reentry_position is not None
                and self.completion.reentry_position > self.spec.deviation):
            raise ValueError('재진입 위치 허용오차는 기존 경로 이탈 한계 이하여야 합니다.')
        self.bundle = build_server_config(load_nav2_parameters(environment['nav_params'], node.root),
            node.config['robot_id'], self.wall, settings, node.mode == 'sim',
            footprint_padding=cfg.get('footprint_padding'))
        self.bundle['spin']['wall_alignment.wait_until_fresh'] = self._sensor_wait_indefinite
        self.odom_frame = self.bundle['costmap']['global_frame']
        self.profile = MotionProfile.from_mapping(self.bundle['profile'])
        self.body_footprint = alignment_footprint(self.bundle['costmap'])
        self._timing = TimingProbe(node)
        self.lock = TimedRLock(self._timing)
        self._output_epoch = 0
        self._validation_busy = threading.Lock()
        self._validation_inputs = threading.local()
        self.latest = {}
        self.wait_status = None
        self._waiting_workers = set()
        self.pause_clock = PauseClock(unlimited=self._sensor_wait_indefinite)
        self._pause_requested = False
        self._controller_wait = (0., False)
        self._pause_session = secrets.randbits(48)
        self._pause_sequence = 0
        self._pause_publisher = node.create_publisher(Float64MultiArray, self.bundle['prefix']+'/handoff_wait_clock', 1)
        self._pause_subscription = node.create_subscription(Bool, self.bundle['prefix']+'/controller_wait',
            self._receive_controller_wait, 1, callback_group=node.callbacks)
        self.poses = WaitingPoses(node.poses, self._retry, self._mark_wait)
        self.window = None
        self.active_context = None
        self.session = None
        self.gate = None
        self.stage = ''
        self.error = ''
        self.speed = None
        self.tracker = None
        self.wall_value = None
        self.wall_error_text = ''
        self.wall_last_stamp = 0
        self.clearance = None
        self.align_origin = self.align_target = self.align_envelope = None
        self.live_guard = None
        self._closed = threading.Event()
        self.bindings = {s: NavigationBinding(v, Nav2Client(node, v, node.callbacks, execution_clock=self.pause_clock.scoped))
                         for s, v in self.profile.navigation.items()}
        self.spin = SpinClient(node, self.profile.spin_endpoint, settings, node.callbacks, execution_clock=self.pause_clock.scoped)
        self.publisher = node.create_publisher(Twist, 'cmd_vel_nav', 1)
        self.wall_publisher = node.create_publisher(PoseStamped, 'handoff/wall_observation', 1)
        self.subscriptions = []
        self._odom_callbacks = MutuallyExclusiveCallbackGroup()
        for key, kind, topic in (
            ('odom', Odometry, self.bundle['odom']),
            ('costmap', Costmap, self.bundle['prefix']+'/local_costmap/costmap_raw'),
            ('footprint', PolygonStamped, self.bundle['prefix']+'/local_costmap/published_footprint'),
            ('scan', LaserScan, self.bundle['scan']),
        ):
            self.subscriptions.append(node.create_subscription(kind, topic,
                lambda msg, k=key: self._receive(k, msg), qos_profile_sensor_data,
                callback_group=self._odom_callbacks if key == 'odom' else node.callbacks))
        for source, topic in (('normal', 'cmd_vel_normal'), ('nav', 'handoff/raw_nav'), ('spin', 'handoff/raw_spin')):
            self.subscriptions.append(node.create_subscription(Twist, topic,
                lambda msg, s=source: self._forward(s, msg), 1, callback_group=node.callbacks))
        self.timer = node.create_timer(.05, self._watchdog, callback_group=node.callbacks)
        self.worker = threading.Thread(target=self._observe, name='handoff_wall', daemon=True)
        self._input_trace = InputTrace(self)
        self.worker.start()

    def _receive_controller_wait(self, msg: Any) -> None:
        with self.lock:
            self._controller_wait = (time.monotonic(), bool(msg.data))

    def _publish_pause_clock(self) -> None:
        with self.lock:
            recent, waiting = self._controller_wait
            wall_wait = (self.stage == 'wall' and waiting and time.monotonic()-recent <= .2
                and len(self.node.get_publishers_info_by_topic(self.bundle['prefix']+'/controller_wait')) == 1)
            trial = getattr(self.node, 'body_trial', None)
            transfer = self.node.transfer
            cancelled = transfer._cancel_requested or (transfer.active and transfer.active[0].is_cancel_requested)
            cancelled = cancelled or (trial is not None and trial.token is not None and trial.cancel.is_set())
            active = not cancelled and self._owned() and not self.error and not self.node.stopping and not self.node.blocked
            active = active and (self._pause_requested or bool(self._waiting_workers)
                or (self.gate is not None and self.gate.enabled and (self.gate.waiting or wall_wait)))
            if active:
                self.publisher.publish(Twist())
            total = self.pause_clock.update(bool(active))
            self._pause_sequence += 1
            self._pause_publisher.publish(Float64MultiArray(data=[float(self._pause_session),
                float(self._pause_sequence), total, self.node.get_clock().now().nanoseconds/1e9]))

    def _receive(self, key: str, msg: Any) -> None:
        self._input_trace.receive("callback_begin", key, msg)
        with self.lock:
            self.latest[key] = (time.monotonic(), msg)
            self._input_trace.receive("stored", key, msg)
            if key == 'odom' and self.speed is not None:
                previous_stamp = self.speed.last_stamp
                try:
                    sign = -1 if self.stage in ('return', 'window') else 1
                    self.speed.observe(stamp(msg), sign*msg.twist.twist.linear.x,
                                       sign*msg.twist.twist.angular.z)
                    if self.speed.sample_gap:
                        self._pause_output('odom 표본 간격: 새 정지 증거 대기')
                except Exception as error:
                    self.error = f'{error}; previous_stamp_ns={previous_stamp}'

    def _read(self, key: str, age_limit: float = .5) -> Any:
        snapshot = getattr(self._validation_inputs, 'snapshot', None)
        if snapshot is None:
            with self.lock:
                pair = self.latest.get(key)
        else:
            pair = snapshot.get(key)
        if pair is None:
            error_type = ScanTemporarilyUnavailable if key == 'scan' and self.wall['controller'].get('observation_wait', 0) > 0 else InputUnavailable
            raise error_type('입력 없음: '+key)
        received, msg = pair
        age = (self.node.get_clock().now().nanoseconds-stamp(msg))/1e9
        receive_age = time.monotonic()-received
        if receive_age > age_limit or not -.1 <= age <= age_limit:
            error_type = ScanTemporarilyUnavailable if key == 'scan' and age >= 0 and self.wall['controller'].get('observation_wait', 0) > 0 else InputUnavailable if age >= 0 else RuntimeError
            raise error_type(self._input_trace.expired(key, received, msg, age_limit,
                receive_age, age, snapshot is not None))
        return msg

    def _session(self) -> str:
        infos = self.node.get_publishers_info_by_topic(self.bundle['odom'])
        if len(infos) != 1:
            raise RuntimeError('단일 odom 발행자 필요')
        return bytes(infos[0].endpoint_gid).hex()

    def invalidate_window(self) -> None:
        with self.lock:
            self.window = None

    def remember_window(self, goal: Any, arrival: dict) -> None:
        reference = WindowEntryReference.from_arrival(goal, arrival)
        with self.lock:
            self.window = reference

    def readiness(self) -> dict:
        """실행 소유권을 요구하지 않는 준비 검사. 실패 항목을 버리지 않는다."""
        failures = []
        for key in ('odom', 'costmap', 'footprint'):
            try:
                self._read(key)
            except Exception as error:
                failures.append({'code': key.upper()+'_INPUT', 'detail': str(error)})
        if self.window is None:
            failures.append({'code': 'WINDOW_MISSING', 'detail': '성공한 window 도착 기록 없음'})
        if self.error:
            failures.append({'code': 'OUTPUT_FAULT', 'detail': self.error})
        try:
            self._session()
        except Exception as error:
            failures.append({'code': 'ODOM_PUBLISHER', 'detail': str(error)})
        topic = '/'+self.node.config['robot_id']+'/cmd_vel_nav'
        if len(self.node.get_publishers_info_by_topic(topic)) != 1:
            failures.append({'code': 'OUTPUT_PUBLISHER', 'detail': '속도 출력 발행자는 하나여야 합니다.'})
        if not self.spin.ready():
            failures.append({'code': 'SPIN_UNAVAILABLE', 'detail': 'Spin 서버 미연결'})
        return {'ready': not failures, 'failures': failures}

    def ready(self) -> bool:
        return self.readiness()['ready']

    def _owned(self) -> bool:
        current = self.node.handoff.current
        return current is not None and current[0] == 'transfer'

    def _pause_output(self, reason: str) -> None:
        with self.lock:
            self._pause_requested = True
            self.pause_clock.update(True)
            if self.wait_status is None:
                self.wait_status = {'since': time.monotonic(), 'reason': reason}
                self.node.get_logger().warning('HANDOFF_WAIT '+reason)
            if self.gate is not None and self.gate.enabled:
                self.gate.hold()
            if self._owned():
                self.publisher.publish(Twist())

    def _mark_wait(self, error: Exception) -> None:
        # TF 제공자의 내부 조회 대기가 시작되는 시점부터 출력도 정지한다.
        with self.lock:
            ticket = getattr(self._validation_inputs, 'retry_ticket', None)
            if ticket is not None:
                self._waiting_workers.add(ticket)
            self._pause_output(str(error))

    def _retry(self, operation: Any, *, check: Any = None) -> Any:
        # ROS 콜백은 기다리지 않는다. worker의 재관측 중에는 출력부도 계속 0이다.
        if getattr(self._validation_inputs, 'nonblocking', False):
            return operation()
        deadline = float('inf') if getattr(self, '_sensor_wait_indefinite', False) else time.monotonic() + self._recovery_timeout
        epoch = self._output_epoch
        previous_deadline = getattr(self._validation_inputs, 'deadline', None)
        if previous_deadline is not None:
            deadline = min(deadline, previous_deadline)
        self._validation_inputs.deadline = deadline
        ticket = object()
        previous_ticket = getattr(self._validation_inputs, 'retry_ticket', None)
        self._validation_inputs.retry_ticket = ticket
        try:
            while True:
                self._check_state()
                if self._output_epoch != epoch:
                    raise RuntimeError('재관측 중 출력 세션 변경')
                if time.monotonic() >= deadline:
                    raise TimeoutError('재관측 제한시간 초과')
                try:
                    if check is not None:
                        check()
                    value = operation()
                    self._check_state()
                    if self._output_epoch != epoch:
                        raise RuntimeError('재관측 중 출력 세션 변경')
                    if time.monotonic() >= deadline:
                        raise TimeoutError('재관측 제한시간 초과')
                    return value
                except (InputUnavailable, TransformUnavailable) as error:
                    with self.lock:
                        self._waiting_workers.add(ticket)
                        self._pause_output(str(error))
                    if time.monotonic() >= deadline:
                        raise TimeoutError('재관측 제한시간 초과: '+str(error)) from error
                    time.sleep(.02)
        finally:
            with self.lock:
                self._waiting_workers.discard(ticket)
                if not self._waiting_workers and (self.gate is None or not self.gate.enabled):
                    self._pause_requested = False
            self._validation_inputs.deadline = previous_deadline
            self._validation_inputs.retry_ticket = previous_ticket

    def check(self) -> None:
        self._retry(self._check_once)

    def _check_once(self) -> None:
        self._check_state()
        for key in ('odom', 'costmap', 'footprint'):
            self._read(key)

    def _check_state(self) -> None:
        trial = getattr(self.node, 'body_trial', None)
        if trial is not None and trial.token is not None and trial.cancel.is_set():
            raise RuntimeError('차체 시험 취소 요청')
        if self.node.stopping or self.node.blocked or not self._owned():
            raise RuntimeError('차체 인계 실행 소유권 또는 노드 상태 오류')
        transfer = self.node.transfer
        if transfer._cancel_requested or (transfer.active and transfer.active[0].is_cancel_requested):
            raise RuntimeError('인계 취소 요청')
        if self.error:
            raise RuntimeError(self.error)
        if self.session is not None and self._session() != self.session:
            raise RuntimeError('odom 발행 세션 변경')
        # 일반 Nav2 출력은 cmd_vel_normal로 들어와야 한다. 우회 발행자는 거절한다.
        if len(self.node.get_publishers_info_by_topic('/'+self.node.config['robot_id']+'/cmd_vel_nav')) != 1:
            raise RuntimeError('속도 출력 경로 우회 발행자 발견')

    def settling_check(self) -> None:
        # 취소 후 Goal 정리에서도 정지 증거는 기다린다. 이동 재개는 하지 않는다.
        deadline = time.monotonic() + self._recovery_timeout
        while True:
            try:
                self._read('odom')
                return
            except InputUnavailable:
                if time.monotonic() >= deadline:
                    raise TimeoutError('정지 확인용 odom 재관측 시간 초과')
                time.sleep(.02)

    def context(self) -> tuple:
        self.check()
        if self.active_context is None:
            raise RuntimeError('활성 window 기준 없음')
        return self.active_context

    def odom_stamp(self) -> int:
        return stamp(self._read('odom'))

    def pose(self, at: int, check: Any) -> tuple:
        check()
        m = self._retry(lambda: self.poses.lookup(
            self.odom_frame, self.settings.base_frame, at or self.odom_stamp(), check), check=check)
        return float(m[0,3]), float(m[1,3]), math.atan2(m[1,0], m[0,0])

    def _odom_pose(self) -> tuple:
        msg=self._read('odom')
        if msg.header.frame_id != self.odom_frame or msg.child_frame_id != self.settings.base_frame:
            raise RuntimeError('차체 odom frame 불일치')
        p,q=msg.pose.pose.position,msg.pose.pose.orientation
        values=(p.x,p.y,q.x,q.y,q.z,q.w)
        if not all(math.isfinite(v) for v in values) or abs(sum(v*v for v in values[2:])-1)>1e-3:
            raise RuntimeError('odom 자세 형식 오류')
        return p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))

    def _observe(self) -> None:
        while not self._closed.wait(.01):
            with self.lock:
                tracker = self.tracker
            if tracker is None:
                continue
            try:
                scan = self._read('scan', self.wall['controller']['observation_age'])
                if stamp(scan) <= self.wall_last_stamp:
                    continue
                check = lambda: self._read('odom')
                record = dict(stamp_ns=stamp(scan), scan={k:getattr(scan,k) for k in
                    ('ranges','angle_min','angle_increment','range_min','range_max')},
                    base_from_scan=self.node.poses.lookup(self.settings.base_frame, scan.header.frame_id, stamp(scan), check),
                    odom_from_base=self.node.poses.lookup(self.odom_frame, self.settings.base_frame, stamp(scan), check))
                value = tracker.observe(record)
                with self.lock:
                    if tracker is not self.tracker:
                        continue
                    self.wall_last_stamp = stamp(scan)
                    if value['ready']:
                        self.wall_value = (time.monotonic(), value)
                        msg = PoseStamped()
                        msg.header.frame_id=self.odom_frame; msg.header.stamp=scan.header.stamp
                        msg.pose.position.x=value['x']; msg.pose.position.y=value['y']
                        msg.pose.orientation.z=math.sin(value['yaw']/2)
                        msg.pose.orientation.w=math.cos(value['yaw']/2)
                        self.wall_publisher.publish(msg)
            except (InputUnavailable, TransformUnavailable):
                # 이전 관측 stamp를 새 시각으로 위장하지 않는다. controller가 0 출력 대기한다.
                continue
            except Exception as error:
                with self.lock:
                    if tracker is self.tracker and tracker.count:
                        self.wall_error_text = str(error)

    def wall_error(self, check: Any) -> tuple:
        return self._retry(lambda: self._wall_error_once(check), check=check)

    def _wall_error_once(self, check: Any) -> tuple:
        with self.lock:
            if self.tracker is None:
                self.tracker = WallTracker(self.wall['observation'])
                self.wall_last_stamp = 0
                self.wall_value = None
                self.wall_error_text = ''
        while True:
            check()
            with self.lock:
                pair, error = self.wall_value, self.wall_error_text
            if error:
                raise RuntimeError(error)
            if pair is not None:
                received, wall = pair
                age = (self.node.get_clock().now().nanoseconds-wall['stamp_ns'])/1e9
                if age < 0:
                    raise RuntimeError('벽 관측 미래 시각')
                if time.monotonic()-received > self.wall['controller']['observation_age'] or age > self.wall['controller']['observation_age']:
                    if self.wall['controller'].get('observation_wait', 0) <= 0:
                        raise RuntimeError('벽 관측 만료')
                    raise InputUnavailable('벽 관측 만료: 새 관측 대기')
                x,y,yaw = self.pose(0, check)
                return ((wall['x']-x)*math.cos(wall['yaw'])+(wall['y']-y)*math.sin(wall['yaw']),
                        wrap(wall['yaw']-yaw))
            raise InputUnavailable('벽 관측 준비 대기')

    def _grid_inputs(self) -> tuple:
        cm, fp = self._read('costmap'), self._read('footprint')
        if cm.header.frame_id != self.odom_frame or fp.header.frame_id != self.odom_frame:
            raise RuntimeError('충돌 입력 frame 불일치')
        points = [(p.x,p.y) for p in fp.polygon.points]
        if len(points) != 4 or not all(math.isfinite(v) for p in points for v in p):
            raise RuntimeError('footprint 형상 오류')
        lengths = lambda ps: sorted(math.dist(ps[i],ps[j]) for i in range(4) for j in range(i))
        if any(abs(a-b)>2e-5 for a,b in zip(lengths(points),lengths(self.body_footprint))):
            raise RuntimeError('footprint 형상 변경')
        return cm, points

    def _grid_key(self, cm: Any) -> str:
        metadata = message_to_ordereddict(cm.metadata)
        # 갱신 시각은 기하 증명 키가 아니다. align은 허용 이동과 모든 회전을 포함하는 고정 영역을 사용한다.
        geometry = {k: metadata[k] for k in ('resolution', 'size_x', 'size_y', 'origin')}
        region = None
        if self.clearance is not None or getattr(self, '_align_preparing', False):
            center, limit = self.align_envelope
            radius = max(math.hypot(x, y) for x, y in self.body_footprint)
            region = (*center, radius + limit)
        return grid_key({'frame': cm.header.frame_id, **geometry}, bytes(cm.data), region=region)

    def _align_pose_valid(self, current: tuple) -> None:
        if self.align_envelope is None:
            raise RuntimeError('회전 공간 한계 누락')
        center, limit = self.align_envelope
        if not all(math.isfinite(v) for v in (*current, *center, limit)):
            raise RuntimeError('방향 조정 비유한 입력')
        distance = math.dist(current[:2], center)
        angle = abs(wrap(current[2]-self.align_origin[2]))
        if distance > limit or angle > math.radians(16):
            detail = (f'방향 조정 범위: 위치={distance:.6f}/{limit:.6f}m, '
                      f'방향={angle:.6f}/{math.radians(16):.6f}rad')
            if self.node.motion.stationary_now():
                raise ClearancePending('정지 자세 재관측 대기: '+detail)
            raise RuntimeError('이동 중 '+detail)

    def alignment_pose(self, center: tuple, limit: float, check: Any, *, origin: tuple | None = None) -> tuple:
        """저장 기준을 바꾸지 않고 정지 표본이 재진입 영역으로 회복되길 기다린다."""
        def observe() -> tuple:
            current = self.pose(0, check)
            if not all(math.isfinite(v) for v in (*current, *center, limit)):
                raise RuntimeError('방향 조정 비유한 입력')
            if math.dist(current[:2], center) > limit:
                if not self.node.motion.stationary_now():
                    raise RuntimeError('이동 중 재진입 위치 범위 초과')
                raise ClearancePending(f'재진입 위치 재관측 대기: {math.dist(current[:2], center):.6f}/{limit:.6f}m')
            if origin is not None:
                angle = abs(wrap(current[2]-origin[2]))
                if not math.isfinite(angle):
                    raise RuntimeError('방향 조정 비유한 방향')
                if angle > math.radians(16):
                    detail = f'방향 조정 각도={angle:.6f}/{math.radians(16):.6f}rad'
                    if not self.node.motion.stationary_now():
                        raise RuntimeError('이동 중 '+detail)
                    raise ClearancePending('정지 방향 재관측 대기: '+detail)
            return current
        return self._retry(observe, check=check)

    def _snapshot(self) -> dict:
        cm, points = self._grid_inputs()
        pose = self._odom_pose()
        self._align_pose_valid(pose)
        return dict(pose=pose, target_yaw=self.align_target, footprint=points,
                    grid=message_to_ordereddict(cm), body_footprint=self.body_footprint,
                    certificate={'pose':pose, 'grid_key':self._grid_key(cm)})

    @traced
    def guard(self, stage: str, path: tuple, check: Any, *, envelope: tuple | None = None) -> Any:
        self.stop_output()
        return self._retry(lambda: self._guard_once(stage, path, check, envelope), check=check)

    def _guard_once(self, stage: str, path: tuple, check: Any, envelope: tuple | None) -> Any:
        if self.clearance is not None:
            self.clearance.close(); self.clearance=None
        with self.lock:
            if stage != 'wall':
                self.tracker=None; self.wall_value=None
        cm, points = self._grid_inputs()
        current=self.pose(0,check)
        # 발행 footprint 시각을 현재 자세와 혼용하지 않고 차체 형상으로 투영한다.
        x,y,yaw=current; c,s=math.cos(yaw),math.sin(yaw)
        footprint=[(x+c*a-s*b,y+s*a+c*b) for a,b in self.body_footprint]
        try:
            check_grid(list(path),footprint,current,message_to_ordereddict(cm))
        except ObstacleBlocked as error:
            if stage != 'align':
                raise
            raise ClearancePending('회전 경로 장애물: '+str(error)) from error
        if stage == 'align':
            self.align_origin=current; self.align_target=path[-1][2]
            self.align_envelope = envelope
            self._align_pose_valid(current)
            self._align_preparing = True
            try:
                self.clearance=AsyncClearance(self._snapshot, response_timeout_s=self._recovery_timeout)
            finally:
                self._align_preparing = False

        def validate_live() -> None:
            check()
            self._grid_inputs()
            if stage == 'window':
                cm, _ = self._grid_inputs()
                pose = self._odom_pose()
                c, s = math.cos(pose[2]), math.sin(pose[2])
                fp = [(pose[0]+c*a-s*b, pose[1]+s*a+c*b) for a,b in self.body_footprint]
                check_grid(list(path), fp, pose, message_to_ordereddict(cm))
            if self.clearance is not None:
                cm, _ = self._grid_inputs()
                current = self._odom_pose()
                self._align_pose_valid(current)
                ready, reason = self.clearance.check(current, self._grid_key(cm),
                    self.node.get_clock().now().nanoseconds, time.monotonic(),
                    max(math.hypot(x,y) for x,y in self.body_footprint))
                if not ready:
                    raise ClearancePending(reason)

        def live() -> None:
            self._retry(validate_live, check=check)

        if self.clearance is not None:
            def prepare() -> None:
                check()
                if not self.node.motion.stationary_now():
                    raise InputUnavailable('회전 검사 준비: 연속 정지 대기')
                validate_live()
            self._retry(prepare, check=check)
        self.live_guard=live
        return live

    def arm_output(self, stage: str) -> None:
        self.check()
        with self.lock:
            self._output_epoch += 1
            self.stage=stage
            self._validation_wait_started = None
            def factory() -> Any:
                return (WallCommandGate(self.wall['controller']['max_linear'], self.wall['controller']['max_angular'])
                    if stage == 'wall' else WindowCommandGate() if stage == 'window'
                    else CommandGate(direction={'departure': 'reverse_left', 'return': 'forward_right',
                        'retreat': 'retreat', 'align': 'align'}[stage]))
            self.gate = TransientCommandGate(factory, self._resume_stopped_stamp, self.settings.settle_s)
            self.speed=MeasuredVelocityGuard(MeasuredVelocityLimits(**(
                self.wall['measured_velocity'] if stage=='wall' else self.policy['measured_velocity'])), allow_sample_gap=True)
            self.gate.arm(time.monotonic())

    def _resume_stopped_stamp(self) -> int | None:
        # 최신 입력과 기존 정지 속도 조건이 모두 성립한 새 표본만 사용한다.
        msg = self._read('odom')
        twist = msg.twist.twist
        v = (twist.linear.x, twist.linear.y, twist.angular.z)
        if (not all(math.isfinite(x) for x in v)
                or math.hypot(v[0], v[1]) >= self.settings.stopped_linear_mps
                or abs(v[2]) >= self.settings.stopped_angular_rps
                or not self.node.motion.stationary_now()):
            return None
        return stamp(msg)

    def stop_navigation_recovery(self) -> None:
        """일반 작업 소유권 동안만 기존 publisher로 0을 보낸다. 인계 gate는 변경하지 않는다."""
        self.node.check()
        with self.lock:
            owner = self.node.handoff.current
            if (not owner or owner[0] != 'work' or self._owned()
                    or self.node.blocked or self.node.stopping or self.error):
                raise RuntimeError('일반 주행 재시도 출력 소유권 상실')
            self.publisher.publish(Twist())

    def stop_output(self) -> None:
        with self.lock:
            self._pause_requested = False
            self.pause_clock.update(False)
            self._output_epoch += 1
            if self.gate is not None:
                self.gate.close()
            self.speed = None
            self.publisher.publish(Twist())

    def _forward_control(self, source: str, msg: Any) -> None:
        # normal 출력은 기존 소유권 검사를 유지하고 무거운 검사를 수행하지 않는다.
        if source == 'normal':
            with self.lock:
                if not self._owned() and not self.node.blocked and not self.node.stopping and not self.error:
                    self.publisher.publish(msg)
            return
        # 재진입 콜백들이 검사 완료를 기다리며 실행기 스레드를 점유하지 않는다.
        if not self._validation_busy.acquire(blocking=False):
            self._timing.add('validation_busy_drop', 1)
            return
        self._validation_inputs.nonblocking = True
        try:
            with self.lock:
                gate = self.gate
                if gate is None or not gate.enabled:
                    return
                epoch, stage = self._output_epoch, self.stage
                guard = self.live_guard
                snapshot = dict(self.latest)
                clearance = self.clearance
            pending = False
            self._validation_inputs.snapshot = snapshot
            try:
                with self._timing.measure('output_validation_s'):
                    self.check()
                    if source != ('spin' if stage == 'align' else 'nav'):
                        if any(abs(v)>1e-9 for v in (msg.linear.x, msg.angular.z)):
                            raise RuntimeError('선택하지 않은 차체 서버 출력')
                        return
                    if any(not math.isfinite(v) or abs(v)>1e-9 for v in
                           (msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y)):
                        raise RuntimeError('평면 외 속도 명령')
                    if guard is not None:
                        try:
                            guard()
                        except ClearancePending:
                            if stage != 'align':
                                raise
                            pending = True
            finally:
                del self._validation_inputs.snapshot
            # 무거운 검사는 끝났다. 최신 입력/취소를 검사한 뒤 짧은 잠금 안에서
            # 동일 단계와 입력인지 재확인하고 실제 publish까지 직렬화한다.
            self.check()
            # grid 해시는 잠금 밖에서 계산한다. 최종 commit에서는 이 costmap
            # 객체가 여전히 최신인지와 최신 odom의 충돌 여유만 짧게 재검증한다.
            align_cm = align_key = None
            if stage == 'align' and clearance is not None:
                align_cm, _ = self._grid_inputs()
                align_key = self._grid_key(align_cm)
            with self.lock:
                if self.gate is not gate or self._output_epoch != epoch or not gate.enabled:
                    return
                trial = getattr(self.node, 'body_trial', None)
                transfer = self.node.transfer
                cancelled = (trial is not None and trial.token is not None and trial.cancel.is_set())
                cancelled = cancelled or transfer._cancel_requested or (transfer.active and transfer.active[0].is_cancel_requested)
                if self.error or self.node.blocked or self.node.stopping or cancelled or not self._owned():
                    self.stop_output()
                    return
                # 검사 중 변경된 입력으로 이전 검사 결과를 승인하지 않는다.
                keys = ('odom', 'costmap', 'footprint')
                changed = any(self.latest.get(k) is not snapshot.get(k) for k in keys)
                # 곡선/직선 이탈은 Nav2가 실행 중 충돌을 검사한다. 이 단계의
                # live_guard 계약은 시각/frame/차체 형상이며 메시지 객체 동일성이 아니다.
                # 자세별 충돌 증명이 필요한 단계나 clearance가 남은 경우는 기존 차단 유지.
                latest_contract = stage in ('departure', 'return', 'retreat', 'wall') and self.clearance is None
                if stage == 'align' and clearance is not None:
                    if self.clearance is not clearance:
                        return
                    self._grid_inputs()
                    current = self._odom_pose()
                    self._align_pose_valid(current)
                    if self.latest.get('costmap', (None, None))[1] is not align_cm:
                        pending = True
                    else:
                        ready, _ = clearance.check(current, align_key,
                            self.node.get_clock().now().nanoseconds, time.monotonic(),
                            max(math.hypot(x,y) for x,y in self.body_footprint))
                        pending = pending or not ready
                elif changed and not latest_contract:
                    self._timing.add('input_changed_drop', 1)
                    self.publisher.publish(Twist())
                    return
                # snapshot 검사는 잠금 밖에서 끝났다. 최종 출력까지 같은 잠금 안에서
                # 최신 odom 및 costmap/footprint의 유효성을 재검사한다. graph/TF 대기 없음.
                self._read('odom')
                if latest_contract:
                    self._grid_inputs()
                    if changed:
                        self._timing.add('input_changed_revalidated', 1)
                # 실제 controller 명령을 수신한 경우에만 0 명령으로 대기한다.
                # watchdog timer가 가짜 heartbeat를 만들지 않는다. 재관측 중에는 0만 출력한다.
                if self._waiting_workers:
                    gate.hold()
                    self.publisher.publish(Twist())
                    return
                if pending:
                    gate.hold()
                    now = time.monotonic()
                    if self._validation_wait_started is None:
                        self._validation_wait_started = now
                    if not getattr(self, '_sensor_wait_indefinite', False) and now - self._validation_wait_started >= self._recovery_timeout:
                        raise TimeoutError('회전 충돌 재검사 대기 시간 초과')
                    msg = Twist()
                    self._timing.add('clearance_wait_zero', 1)
                else:
                    self._validation_wait_started = None
                if not gate.accept(msg.linear.x, msg.angular.z, time.monotonic()):
                    raise RuntimeError(gate.error or '출력 차단')
                if not self.gate.waiting:
                    self._pause_requested = False
                if not self.gate.waiting and self.wait_status is not None:
                    self.node.get_logger().info('HANDOFF_RESUMED '+self.wait_status['reason'])
                    self.wait_status = None
                self.publisher.publish(Twist() if self.gate.waiting else msg)
        except (InputUnavailable, TransformUnavailable) as error:
            with self.lock:
                if 'epoch' in locals() and self.gate is gate and self._output_epoch == epoch:
                    self._pause_output(str(error))
        except Exception as error:
            with self.lock:
                # 이전 단계의 늦은 결과/오류가 새 단계를 덮어쓰지 않는다.
                if 'epoch' in locals() and self.gate is gate and self._output_epoch == epoch:
                    self.error = str(error)
                    self.stop_output()
        finally:
            self._validation_inputs.nonblocking = False
            self._validation_busy.release()

    def _watchdog_control(self) -> None:
        with self.lock:
            if self._owned() and self.gate is not None and self.gate.enabled:
                try:
                    for key in ('odom', 'costmap', 'footprint'):
                        self._read(key)
                except InputUnavailable as error:
                    self._pause_output(str(error))
                except Exception as error:
                    self.error = str(error)
                    self.stop_output()
            if self.gate is not None and self.gate.expired(time.monotonic()):
                self.error=self.gate.error
                self.stop_output()
            elif self._owned() and (self.gate is None or not self.gate.enabled or getattr(self.gate, 'waiting', False)):
                self.publisher.publish(Twist())

    @traced
    def build_body(self) -> Any:
        self.check()
        with self.lock:
            if self.window is None:
                raise RuntimeError('성공한 window 도착 기준 없음')
            reference = self.window
            window_id, xy = reference.window_id, reference.xy
            self.session=self._session()
            self.active_context=(self.node.config['map_id'],window_id,self.session)
        if self._input_trace is not None: self._input_trace.emit('tf_pair_begin')
        _, matrices = self.poses.lookup_available_pair(
            (self.settings.map_frame, self.odom_frame), self.settings.base_frame,
            self.odom_stamp, self.check)
        if self._input_trace is not None: self._input_trace.emit('tf_pair_end')
        current = matrices[0]
        reference.check_position((float(current[0,3]), float(current[1,3])))
        planner=HandoffPlanner(poses=self.poses,motion=self.node.motion,inputs=self,
            guard=self.guard,wall=self.wall['controller'],spec=self.spec,window_xy=xy,
            map_frame=self.settings.map_frame,odom_frame=self.odom_frame,base_frame=self.settings.base_frame,
            policy=self.completion, window_correction=True)
        return build_vicpinky_motion(profile=self.profile,bindings=self.bindings,spin=self.spin,
            spin_endpoint=self.profile.spin_endpoint,node=self.node,motion=self.node.motion,
            planner=planner,check=self.check,settling_check=self.settling_check,
            arm_output=self.arm_output,stop_output=self.stop_output,
            record=lambda row:self.node.navigation_log.append(row))

    def close(self) -> None:
        self.stop_output()
        self._closed.set();self.worker.join(timeout=5.)
        if self.worker.is_alive():
            raise RuntimeError('벽 관측 작업 종료 미확인')
        if self.clearance is not None: self.clearance.close()
        self.node.destroy_timer(self.timer)
        self.node.destroy_subscription(self._pause_subscription)
        self.node.destroy_publisher(self._pause_publisher)
        self._input_trace.close()
        for sub in self.subscriptions: self.node.destroy_subscription(sub)
        for binding in self.bindings.values(): binding.client.close()
        self.spin.close()
        self.node.destroy_publisher(self.wall_publisher)
        self.node.destroy_publisher(self.publisher)

    def _watchdog(self) -> None:
        with self._timing.measure('watchdog_s'):
            self._watchdog_control()
        self._timing.emit()
        self._input_trace.tick()
        self._publish_pause_clock()

    def _forward(self, source: str, msg: Any) -> None:
        with self._timing.measure('forward_total_s'):
            self._forward_control(source, msg)
