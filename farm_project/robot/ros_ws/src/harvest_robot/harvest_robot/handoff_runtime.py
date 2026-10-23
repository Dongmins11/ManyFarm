from .handoff_locking import TimingProbe, TimedRLock
"""수확 Node의 센서·서버·단일 출력 연결. 명시 선택한 실물 환경에서만 생성한다."""
import math
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
from farm_navigation.arc_clearance import check_grid
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


class HandoffRuntime:
    def __init__(self, node: Any, environment: dict, settings: Any) -> None:
        if node.mode != 'real' or settings.tf_recovery_enabled:
            raise ValueError('실물 Twist 단일 출력 환경이 필요합니다.')
        self.node, self.settings = node, settings
        cfg = node.config['handoff_runtime']
        self.wall = read_mapping(resolve_file(node.root, cfg['wall_config']))
        self.policy = read_mapping(resolve_file(node.root, cfg['monitor_policy']))
        self.spec = ArcSpec(**cfg['arc'])
        self.completion = CompletionPolicy(**cfg.get('completion', {}))
        if (self.completion.reentry_position is not None
                and self.completion.reentry_position > self.spec.deviation):
            raise ValueError('재진입 위치 허용오차는 기존 경로 이탈 한계 이하여야 합니다.')
        self.bundle = build_server_config(load_nav2_parameters(environment['nav_params'], node.root),
            node.config['robot_id'], self.wall, settings, False)
        self.profile = MotionProfile.from_mapping(self.bundle['profile'])
        self.body_footprint = alignment_footprint(self.bundle['costmap'])
        self._timing = TimingProbe(node)
        self.lock = TimedRLock(self._timing)
        self._output_epoch = 0
        self._validation_busy = threading.Lock()
        self._validation_inputs = threading.local()
        self.latest = {}
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
        self.align_origin = self.align_target = None
        self.live_guard = None
        self._closed = threading.Event()
        self.bindings = {s: NavigationBinding(v, Nav2Client(node, v, node.callbacks))
                         for s, v in self.profile.navigation.items()}
        self.spin = SpinClient(node, self.profile.spin_endpoint, settings, node.callbacks)
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
            raise RuntimeError('입력 없음: '+key)
        received, msg = pair
        age = (self.node.get_clock().now().nanoseconds-stamp(msg))/1e9
        receive_age = time.monotonic()-received
        if receive_age > age_limit or not -.1 <= age <= age_limit:
            raise RuntimeError(self._input_trace.expired(key, received, msg, age_limit,
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

    def check(self) -> None:
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
        self._read('odom')
        # 일반 Nav2 출력은 cmd_vel_normal로 들어와야 한다. 우회 발행자는 거절한다.
        if len(self.node.get_publishers_info_by_topic('/'+self.node.config['robot_id']+'/cmd_vel_nav')) != 1:
            raise RuntimeError('속도 출력 경로 우회 발행자 발견')

    def settling_check(self) -> None:
        self._read('odom')

    def context(self) -> tuple:
        self.check()
        if self.active_context is None:
            raise RuntimeError('활성 window 기준 없음')
        return self.active_context

    def odom_stamp(self) -> int:
        return stamp(self._read('odom'))

    def pose(self, at: int, check: Any) -> tuple:
        check()
        at = at or self.odom_stamp()
        m = self.node.poses.lookup('odom', self.settings.base_frame, at, check)
        return float(m[0,3]), float(m[1,3]), math.atan2(m[1,0], m[0,0])

    def _odom_pose(self) -> tuple:
        msg=self._read('odom')
        if msg.header.frame_id != 'odom' or msg.child_frame_id != self.settings.base_frame:
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
                check = self.settling_check
                record = dict(stamp_ns=stamp(scan), scan={k:getattr(scan,k) for k in
                    ('ranges','angle_min','angle_increment','range_min','range_max')},
                    base_from_scan=self.node.poses.lookup(self.settings.base_frame, scan.header.frame_id, stamp(scan), check),
                    odom_from_base=self.node.poses.lookup('odom', self.settings.base_frame, stamp(scan), check))
                value = tracker.observe(record)
                with self.lock:
                    if tracker is not self.tracker:
                        continue
                    self.wall_last_stamp = stamp(scan)
                    if value['ready']:
                        self.wall_value = (time.monotonic(), value)
                        msg = PoseStamped()
                        msg.header.frame_id='odom'; msg.header.stamp=scan.header.stamp
                        msg.pose.position.x=value['x']; msg.pose.position.y=value['y']
                        msg.pose.orientation.z=math.sin(value['yaw']/2)
                        msg.pose.orientation.w=math.cos(value['yaw']/2)
                        self.wall_publisher.publish(msg)
            except Exception as error:
                with self.lock:
                    if tracker is self.tracker and tracker.count:
                        self.wall_error_text = str(error)

    def wall_error(self, check: Any) -> tuple:
        with self.lock:
            if self.tracker is None:
                self.tracker = WallTracker(self.wall['observation'])
                self.wall_last_stamp = 0
                self.wall_value = None
                self.wall_error_text = ''
        deadline = time.monotonic()+self.settings.readiness_timeout_s
        while True:
            check()
            with self.lock:
                pair, error = self.wall_value, self.wall_error_text
            if error:
                raise RuntimeError(error)
            if pair is not None:
                received, wall = pair
                age = (self.node.get_clock().now().nanoseconds-wall['stamp_ns'])/1e9
                if time.monotonic()-received > self.wall['controller']['observation_age'] or not 0 <= age <= self.wall['controller']['observation_age']:
                    raise RuntimeError('벽 관측 만료')
                x,y,yaw = self.pose(0, check)
                return ((wall['x']-x)*math.cos(wall['yaw'])+(wall['y']-y)*math.sin(wall['yaw']),
                        wrap(wall['yaw']-yaw))
            if time.monotonic() >= deadline:
                raise TimeoutError('벽 관측 준비 시간 초과')
            time.sleep(.01)

    def _grid_inputs(self) -> tuple:
        cm, fp = self._read('costmap'), self._read('footprint')
        if cm.header.frame_id != 'odom' or fp.header.frame_id != 'odom':
            raise RuntimeError('충돌 입력 frame 불일치')
        points = [(p.x,p.y) for p in fp.polygon.points]
        if len(points) != 4 or not all(math.isfinite(v) for p in points for v in p):
            raise RuntimeError('footprint 형상 오류')
        lengths = lambda ps: sorted(math.dist(ps[i],ps[j]) for i in range(4) for j in range(i))
        if any(abs(a-b)>2e-5 for a,b in zip(lengths(points),lengths(self.body_footprint))):
            raise RuntimeError('footprint 형상 변경')
        return cm, points

    def _grid_key(self, cm: Any) -> str:
        radius=max(math.hypot(x,y) for x,y in self.body_footprint)
        return grid_key({'frame':cm.header.frame_id, **message_to_ordereddict(cm.metadata)},
                        bytes(cm.data), (*self.align_origin[:2], radius+.005))

    def _snapshot(self) -> dict:
        cm, points = self._grid_inputs()
        pose = self._odom_pose()
        return dict(pose=pose, target_yaw=self.align_target, footprint=points,
                    grid=message_to_ordereddict(cm), body_footprint=self.body_footprint,
                    certificate={'pose':pose, 'grid_key':self._grid_key(cm)})

    @traced
    def guard(self, stage: str, path: tuple, check: Any) -> Any:
        self.stop_output()
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
        check_grid(list(path),footprint,current,message_to_ordereddict(cm))
        if stage == 'align':
            self.align_origin=current; self.align_target=path[-1][2]
            self.clearance=AsyncClearance(self._snapshot)

        def live() -> None:
            check()
            self._grid_inputs()
            if stage == 'window':
                cm, _ = self._grid_inputs()
                pose = self._odom_pose()
                c, s = math.cos(pose[2]), math.sin(pose[2])
                fp = [(pose[0]+c*a-s*b, pose[1]+s*a+c*b) for a,b in self.body_footprint]
                check_grid(list(path), fp, pose, message_to_ordereddict(cm))
            if self.clearance is not None:
                cm,_ = self._grid_inputs()
                current=self._odom_pose()
                if math.dist(current[:2],self.align_origin[:2])>.005:
                    raise RuntimeError('회전 중 위치 이탈')
                ready, reason=self.clearance.check(current,self._grid_key(cm),
                    self.node.get_clock().now().nanoseconds,time.monotonic(),
                    max(math.hypot(x,y) for x,y in self.body_footprint))
                if not ready:
                    raise RuntimeError(reason)
        if self.clearance is not None:
            deadline=time.monotonic()+3.
            while True:
                check()
                if not self.node.motion.stationary_now():
                    raise RuntimeError('회전 검사 준비 중 정지 상실')
                cm,_=self._grid_inputs()
                ready,reason=self.clearance.check(current,self._grid_key(cm),
                    self.node.get_clock().now().nanoseconds,time.monotonic(),
                    max(math.hypot(x,y) for x,y in self.body_footprint))
                if ready: break
                if time.monotonic()>deadline: raise TimeoutError(reason)
                time.sleep(.01)
        self.live_guard=live
        return live

    def arm_output(self, stage: str) -> None:
        self.check()
        with self.lock:
            self._output_epoch += 1
            self.stage=stage
            self.gate=(WallCommandGate(self.wall['controller']['max_linear'],self.wall['controller']['max_angular'])
                if stage=='wall' else WindowCommandGate() if stage=='window' else CommandGate(direction={'departure':'reverse_left','return':'forward_right',
                                                             'retreat':'retreat','align':'align'}[stage]))
            self.speed=MeasuredVelocityGuard(MeasuredVelocityLimits(**(
                self.wall['measured_velocity'] if stage=='wall' else self.policy['measured_velocity'])))
            self.gate.arm(time.monotonic())

    def stop_output(self) -> None:
        with self.lock:
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
        try:
            with self.lock:
                gate = self.gate
                if gate is None or not gate.enabled:
                    return
                epoch, stage = self._output_epoch, self.stage
                guard = self.live_guard
                snapshot = dict(self.latest)
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
                        guard()
            finally:
                del self._validation_inputs.snapshot
            # 무거운 검사는 끝났다. 최신 입력/취소를 검사한 뒤 짧은 잠금 안에서
            # 동일 단계와 입력인지 재확인하고 실제 publish까지 직렬화한다.
            self.check()
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
                latest_contract = stage in ('departure', 'return', 'retreat') and self.clearance is None
                if changed and not latest_contract:
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
                if not gate.accept(msg.linear.x, msg.angular.z, time.monotonic()):
                    raise RuntimeError(gate.error or '출력 차단')
                self.publisher.publish(msg)
        except Exception as error:
            with self.lock:
                # 이전 단계의 늦은 결과/오류가 새 단계를 덮어쓰지 않는다.
                if 'epoch' in locals() and self.gate is gate and self._output_epoch == epoch:
                    self.error = str(error)
                    self.stop_output()
        finally:
            self._validation_busy.release()

    def _watchdog_control(self) -> None:
        with self.lock:
            if self.gate is not None and self.gate.expired(time.monotonic()):
                self.error=self.gate.error
                self.stop_output()
            elif self._owned() and (self.gate is None or not self.gate.enabled):
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
        _, matrices = self.node.poses.lookup_available_pair(
            (self.settings.map_frame, 'odom'), self.settings.base_frame,
            self.odom_stamp, self.check)
        if self._input_trace is not None: self._input_trace.emit('tf_pair_end')
        current = matrices[0]
        reference.check_position((float(current[0,3]), float(current[1,3])))
        planner=HandoffPlanner(poses=self.node.poses,motion=self.node.motion,inputs=self,
            guard=self.guard,wall=self.wall['controller'],spec=self.spec,window_xy=xy,
            map_frame=self.settings.map_frame,odom_frame='odom',base_frame=self.settings.base_frame,
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

    def _forward(self, source: str, msg: Any) -> None:
        with self._timing.measure('forward_total_s'):
            self._forward_control(source, msg)
