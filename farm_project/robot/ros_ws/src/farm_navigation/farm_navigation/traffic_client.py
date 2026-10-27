"""관제 계약의 로봇 측 상태 관리. 허가 대기는 I/O 스레드, 보고/등록은 ROS 콜백이다."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import math
import threading
import time
from typing import Any, Callable

from action_msgs.msg import GoalStatus
from action_msgs.srv import CancelGoal
from geometry_msgs.msg import Twist
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from farm_interfaces.action import AcquirePassage
from farm_interfaces.msg import TrafficContext, TrafficControlState, TrafficProgress
from farm_interfaces.srv import GetPassageState, ReleasePassage
from .traffic_contract import TrafficIds, TrafficRegistry
from .configuration import resolve_file
from .route import RouteGraph


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def context_key(context: Any) -> tuple:
    return tuple(getattr(context,k) for k in ('robot_id','boot_id','request_id','server_epoch'))


class TrafficClient:
    """로봇당 하나. 관제의 공간 관리나 시간 만료 정책을 로봇에 복제하지 않는다."""
    def __init__(self, node: Any, root: Path, profile: dict, settings: Any, task_id: Callable[[],str]) -> None:
        self.node, self.settings = node, settings
        self.task_id = task_id
        config = profile['traffic']
        self.registry = TrafficRegistry(resolve_file(root, config['registry']),
                                        RouteGraph(profile['route_graph']), profile['robot_id'])
        if self.registry.data['map']['map_id'] != profile['map_id']:
            raise ValueError('교통 등록 map_id 불일치')
        self.lock = threading.RLock()
        self.ids = TrafficIds(root / config['state_file'], profile['robot_id'])
        self.robot_id, self.boot_id = profile['robot_id'], self.ids.next('boot')
        self.epoch = self.sync = ''
        self.control = None
        self.verified = False
        self.generation = 0
        self.status_sequence = self.progress_sequence = self.route_revision = 0
        self.latest_stamp = self.sync_after = 0
        self.position_status = 0
        self.occupied: set[str] = set()
        self.pose_valid = False
        self.stopped = False
        self.moving = False
        self.fault = ''
        self.work_interrupted = False
        self.current = None
        self.pending = None
        self.permits: list[dict] = []
        self.query = None
        self.release = None
        self.discovery_needed = True
        self.reset_epoch = None
        self.observed_epoch = None
        self.server_was_ready = False
        self.last_ros = node.get_clock().now().nanoseconds
        self.last_report = self.last_ros
        self.status_publish: Callable | None = None
        self.motion_clients = []
        self.group = MutuallyExclusiveCallbackGroup()
        reliable = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE)
        transient = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                               durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.progress_pub = node.create_publisher(TrafficProgress, 'traffic_progress', reliable)
        self.control_sub = node.create_subscription(TrafficControlState, '/traffic/control_state', self._control, transient, callback_group=self.group)
        self.acquire_client = ActionClient(node, AcquirePassage, '/traffic/acquire_passage', callback_group=self.group)
        self.get_client = node.create_client(GetPassageState, '/traffic/get_passage_state', callback_group=self.group)
        self.release_client = node.create_client(ReleasePassage, '/traffic/release_passage', callback_group=self.group)
        self.stop_pubs = [node.create_publisher(Twist, topic, 10) for topic in ('cmd_vel_nav','cmd_vel')]
        # 재시작 이전 프로세스의 주행도 해당 로봇의 지정 Action에서 취소한다.
        self.startup_cancels = [node.create_client(CancelGoal, endpoint.rstrip('/')+'/_action/cancel_goal', callback_group=self.group)
                               for endpoint in (settings.follow_action, settings.navigate_action)]
        self.cancel_sent: set[int] = set()
        self.timer = node.create_timer(.05, self._tick, callback_group=self.group,
                                      clock=Clock(clock_type=ClockType.STEADY_TIME))
        self._stop()

    def _stop(self) -> None:
        for publisher in self.stop_pubs:
            publisher.publish(Twist())
        for client in self.motion_clients:
            client.request_stop()
        self.stopped = True
        self.moving = False

    def _invalidate(self, reason: str) -> None:
        if self.query is not None:
            self.get_client.remove_pending_request(self.query)
            self.query = None
        self.work_interrupted = self.work_interrupted or self.current is not None
        self.generation += 1
        self.verified = False
        self.discovery_needed = True
        self.fault = reason
        self._stop()
        if self.pending and self.pending.get('handle') is not None:
            self.pending['handle'].cancel_goal_async()

    def _control(self, message: Any) -> None:
        with self.lock:
            if message.server_epoch != self.epoch:
                # 다른 세대 Topic만으로 세대를 선택하지 않는다. 조회 결과를 기준으로 삼는다.
                if message.server_epoch != self.observed_epoch:
                    self.observed_epoch = message.server_epoch
                    self._invalidate('관제 세대 확인 필요')
                return
            self._apply_control(message)

    def _apply_control(self, message: Any) -> None:
        if self.control is not None and message.server_epoch == self.control.server_epoch and message.state_sequence <= self.control.state_sequence:
            return
        if message.phase not in ('WAIT_STOP','WAIT_POSITION','RECONCILING','READY'):
            self._invalidate('알 수 없는 관제 상태'); return
        self.control = deepcopy(message)
        registrations = [r for r in message.robots if r.robot_id == self.robot_id and r.boot_id == self.boot_id]
        registration = registrations[0] if len(registrations) == 1 else None
        if message.zone_revision != self.registry.data['zone_revision']:
            self.fault = '구역 버전 불일치'; self._stop(); return
        if registration is None:
            self._stop(); return
        if registration.sync_id != self.sync:
            self.work_interrupted = self.work_interrupted or self.current is not None
            self.sync = registration.sync_id
            self.sync_after = max(self.latest_stamp, self.node.get_clock().now().nanoseconds)
            self.position_status = 0
            self.generation += 1
            self._stop()
        if not self.ready:
            if self.moving: self.generation += 1
            self._stop()
        self._report()

    @property
    def registration(self) -> Any:
        if self.control is None:
            return None
        return next((r for r in self.control.robots if r.robot_id == self.robot_id and r.boot_id == self.boot_id and r.sync_id == self.sync), None)

    @property
    def ready(self) -> bool:
        r = self.registration
        return bool(self.verified and self.control and self.control.phase == 'READY'
                    and self.control.zone_revision == self.registry.data['zone_revision']
                    and r and r.registration_state == 'REGISTERED'
                    and r.accepted_status_sequence > 0 and self.position_status > 0
                    and r.accepted_status_sequence <= self.status_sequence and self.pose_valid
                    and self.reset_epoch != self.epoch)

    def on_status(self, status: Any, stamp_ns: int) -> None:
        """발행한 정확한 Status를 참조한다. 유효하지 않은 위치는 공간 반납에 사용하지 않는다."""
        with self.lock:
            if status.boot_id != self.boot_id or status.robot_id != self.robot_id:
                raise ValueError('RobotStatus/Traffic 식별자가 다릅니다.')
            if status.sequence <= self.status_sequence:
                raise ValueError('RobotStatus 순번은 boot 내에서 증가해야 합니다.')
            previous_occupancy = self.occupied.copy()
            previous_position = self.position_status
            self.status_sequence = status.sequence
            now = self.node.get_clock().now().nanoseconds
            self.pose_valid = stamp_ns > 0 and stamp_ns <= now and 'POSE_UNAVAILABLE' not in status.error_message
            if self.pose_valid:
                p = status.pose.position
                self.occupied = self.registry.occupied(p.x,p.y,status.pose.yaw)
                self.latest_stamp = stamp_ns
                r = self.registration
                if r and r.registration_state == 'WAIT_POSITION' and stamp_ns > self.sync_after:
                    self.position_status = status.sequence
                for permit in self.permits:
                    permit['seen'].update(self.occupied & permit['zones'])
                    if permit is self.current and self.moving:
                        points = permit['points']
                        candidates = [(math.dist((p.x,p.y),xy),i) for i,xy in enumerate(points) if i >= permit['cursor']]
                        if candidates:
                            distance,index = min(candidates)
                            if distance <= self.settings.max_start_distance_m:
                                permit['cursor'] = index
            elif self.moving:
                self.fault = '위치 확인 불가'; self._stop()
            if previous_occupancy != self.occupied or previous_position != self.position_status:
                self._report()
            self._release_exited()

    def _context(self) -> Any:
        if self.current and self.current['context'].server_epoch == self.epoch and self.ready:
            return deepcopy(self.current['context'])
        if self.pending and self.ready:
            return deepcopy(self.pending['goal'].context)
        return TrafficContext(robot_id=self.robot_id, boot_id=self.boot_id, server_epoch=self.epoch)

    def _report(self) -> None:
        if not self.epoch or not self.sync or not self.status_sequence:
            return
        r = self.registration
        stage = 'NONE'
        if r and r.registration_state == 'WAIT_STOP':
            stage = 'STOP_SENT'
        elif r and r.registration_state == 'WAIT_POSITION':
            if not self.position_status:
                return
            stage = 'POSITION_READY'
        if not self.pose_valid and stage != 'STOP_SENT':
            return
        self.progress_sequence += 1
        msg = TrafficProgress(context=self._context(), sync_id=self.sync, sync_stage=stage,
              registered_zone_revision=self.registry.data['zone_revision'], sequence=self.progress_sequence,
              status_sequence=self.status_sequence, traffic_state='MOVING' if self.moving else 'HOLDING' if self.current and self.ready else 'WAITING',
              occupied_zone_ids=sorted(self.occupied), stopped=self.stopped,
              reason_code='RECOVERY_REQUIRED' if self.fault else 'WAITING_PERMISSION' if self.pending or not self.ready else 'NONE', timestamp=timestamp())
        self.progress_pub.publish(msg)

    def _discover(self) -> None:
        if self.query is not None or not self.get_client.service_is_ready():
            return
        req = GetPassageState.Request(robot_id=self.robot_id, caller_boot_id=self.boot_id,
                                      target_boot_id=self.boot_id, query_id=self.ids.next('query'), timestamp=timestamp())
        token = self.generation
        self.query = self.get_client.call_async(req)
        self.query.add_done_callback(lambda f:self._discovered(f,req,token))

    def _discovered(self, future: Any, request: Any, token: int) -> None:
        with self.lock:
            if future is not self.query:
                return
            self.query = None
            if token != self.generation:
                return
            try:
                response = future.result()
                if response.query_id != request.query_id or response.error_code != 'NONE' or response.current_server_epoch != response.control_state.server_epoch or not response.current_server_epoch:
                    raise RuntimeError('관제 조회 응답 불일치')
                new_epoch = response.current_server_epoch
                if self.epoch != new_epoch:
                    if self.pending is not None:
                        self.pending['abandoned'] = True
                        self.pending = None
                    if self.release is not None:
                        self.release_client.remove_pending_request(self.release)
                        self.release = None
                    self.current = None
                    self.permits.clear()  # 관제의 이전 예약은 유지된다. 로컬에서 해제하지 않는다.
                    self.control = None
                    self.sync = ''
                    self.epoch = new_epoch
                self.discovery_needed = False
                self.verified = self.reset_epoch != new_epoch
                self.fault = ''
                self._apply_control(response.control_state)
            except Exception as error:
                self.discovery_needed = False  # 응답 오류는 주기적 자동 재요청하지 않는다.
                self.fault = str(error)
                self.node.get_logger().error(self.fault)

    def _tick(self) -> None:
        with self.lock:
            now = self.node.get_clock().now().nanoseconds
            if now < self.last_ros:
                self.reset_epoch = self.epoch
                self._invalidate('CLOCK_RESET: 새 관제 epoch 필요')
                self.sync_after = now
                self.latest_stamp = 0
                self.pose_valid = False
                self.control = None
            self.last_ros = now
            for i,client in enumerate(self.startup_cancels):
                if i not in self.cancel_sent and client.service_is_ready():
                    client.call_async(CancelGoal.Request())
                    self.cancel_sent.add(i)
            server_ready = self.get_client.service_is_ready()
            if self.server_was_ready and not server_ready:
                self._invalidate('관제 재연결 확인 필요')
            if server_ready and not self.server_was_ready:
                self.discovery_needed = True
            self.server_was_ready = server_ready
            if self.discovery_needed:
                self._discover()
            if now-self.last_report >= 1_000_000_000 or now < self.last_report:
                self.last_report = now
                self._report()
            if not self.ready:
                # /clock 일시정지 중에도 정지 명령 경로는 살아 있다.
                for publisher in self.stop_pubs:
                    publisher.publish(Twist())

    def begin_task(self) -> None:
        """상위 업무가 새로 시작할 때만 복구 후 실행을 허용한다. 중단된 업무를 자동 재개하지 않는다."""
        with self.lock:
            self.work_interrupted = False

    def check_work(self) -> None:
        with self.lock:
            if self.work_interrupted:
                raise RuntimeError('TRAFFIC_INTERRUPTED: 관제 초기화/복구로 업무를 중단합니다.')

    def check(self, generation: int) -> None:
        with self.lock:
            if generation != self.generation or not self.ready or not self.current or self.fault:
                raise RuntimeError('TRAFFIC_INTERRUPTED: 현재 등록/허가로 주행할 수 없습니다. '+self.fault)

    def _wait(self, future: Any, check: Callable[[],None]) -> Any:
        while not future.done():
            check()
            time.sleep(.02)
        check()
        return future.result()

    def acquire(self, path: Any, check: Callable[[],None], task_id: str = '') -> tuple[Any,int]:
        """허가 대기에는 시간 제한이 없다. 호출자는 ROS executor와 다른 I/O 스레드다."""
        if path is None or path.header.frame_id != self.settings.map_frame:
            raise RuntimeError('교통 활성 시 등록 그래프의 명시적 FollowPath가 필요합니다.')
        route = self.registry.route([(p.pose.position.x,p.pose.position.y) for p in path.poses], self.settings.max_start_distance_m)
        task_id = task_id or self.task_id()
        if not task_id:
            raise ValueError('교통 허가 요청에는 원 업무 task_id가 필요합니다.')
        while True:
            check()
            with self.lock:
                if self.fault and self.verified:
                    raise RuntimeError('TRAFFIC_RECOVERY_REQUIRED: '+self.fault)
                if self.ready and self.acquire_client.server_is_ready():
                    break
            time.sleep(.02)
        with self.lock:
            if self.pending is not None:
                raise RuntimeError('이전 교통 요청 정리가 완료되지 않았습니다.')
            generation = self.generation
            self.route_revision += 1
            ctx = TrafficContext(robot_id=self.robot_id, boot_id=self.boot_id,
                                 request_id=self.ids.next('req'), server_epoch=self.epoch)
            goal = AcquirePassage.Goal(context=ctx, sync_id=self.sync, task_id=task_id,
                map_id=self.registry.data['map']['map_id'], map_revision=self.registry.data['map']['map_revision'],
                graph_id=self.registry.graph_id, graph_revision=self.registry.graph_config['graph_revision'],
                zone_revision=self.registry.data['zone_revision'], route_revision=str(self.route_revision),
                route_node_ids=list(route.nodes), route_edge_ids=list(route.edges), stop_node_id=route.nodes[-1],
                footprint_profile_id=self.registry.participant['footprint_profile_id'])
            request = {'goal':goal,'handle':None,'abandoned':False,'feedback_sequence':0,'blocked':None,
                       'route':route,'generation':generation,
                       'points':[(p.pose.position.x,p.pose.position.y) for p in path.poses]}
            self.pending = request
            future = self.acquire_client.send_goal_async(goal, feedback_callback=lambda f:self._feedback(request,f.feedback))
            request['future'] = future
            future.add_done_callback(lambda f:self._accepted(request,f))
        def waiting_check() -> None:
            check()
            with self.lock:
                if generation != self.generation or not self.ready or self.fault:
                    raise RuntimeError('TRAFFIC_INTERRUPTED: 허가 대기 중 등록 변경 또는 오류')
        try:
            handle = self._wait(future,waiting_check)
            if not handle.accepted:
                raise RuntimeError('관제 경로 요청 접수 거절')
            # _accepted 콜백과 동일한 result Future를 공유한다.
            while 'result_future' not in request:
                waiting_check(); time.sleep(.01)
            while not request['result_future'].done():
                waiting_check()
                alternative = self._alternative(request, path)
                if alternative is not None:
                    with self.lock:
                        request['abandoned'] = True
                        handle.cancel_goal_async()
                    # 취소/발급 경합의 terminal과 조회를 먼저 확인한다. 시간 제한 재전송 없음.
                    self._wait(request['result_future'], waiting_check)
                    while self.pending is request:
                        waiting_check(); time.sleep(.01)
                    return self.acquire(alternative, check, task_id)
                time.sleep(.02)
            response = self._wait(request['result_future'],waiting_check)
            with self.lock:
                result = response.result
                self._validate_grant(request,response)
                permit = self._remember(request,result)
                self.current = permit
                self.pending = None
                self.moving = True
                self.stopped = False
                self.fault = ''
                self._report()
                return path, generation
        except BaseException:
            with self.lock:
                request['abandoned'] = True
                self._stop()
                if request['handle'] is not None:
                    request['handle'].cancel_goal_async()
                if request.get('result_future') is not None and request['result_future'].done():
                    self._terminal(request,request['result_future'])
            raise

    def _feedback(self, request: dict, feedback: Any) -> None:
        with self.lock:
            if request is not self.pending or context_key(feedback.context) != context_key(request['goal'].context):
                return
            if feedback.feedback_sequence <= request['feedback_sequence']:
                return
            if (feedback.request_state != 'WAITING' or feedback.context.permit_id
                or any(n not in self.registry.nodes for n in feedback.blocked_node_ids)
                or any(e not in self.registry.edges for e in feedback.blocked_edge_ids)):
                self.fault = '교통 Feedback의 상태 또는 그래프 ID 오류'
                self._stop(); return
            request['feedback_sequence'] = feedback.feedback_sequence
            blocked = (tuple(feedback.blocked_node_ids), tuple(feedback.blocked_edge_ids))
            if blocked != request['blocked']:
                request['blocked'] = blocked
                request['changed'] = True

    def _alternative(self, request: dict, path: Any) -> Any:
        """차단 목록 변경 때만 기존 공통 그래프로 우회한다. 경로가 없으면 원 요청을 유지한다."""
        with self.lock:
            if not request.pop('changed', False): return None
            blocked_nodes, blocked_edges = request['blocked']
        if not blocked_nodes and not blocked_edges: return None
        from .path_builder import build_path
        start = path.poses[0].pose.position
        end = path.poses[-1].pose.position
        q = path.poses[-1].pose.orientation
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        try:
            plan = self.registry.graph.plan((start.x,start.y),(end.x,end.y),
                self.settings.max_start_distance_m,self.settings.max_goal_distance_m,
                blocked_nodes=frozenset(blocked_nodes),
                blocked_edges=self.registry.blocked_work_edges(blocked_nodes, blocked_edges))
            alternative = build_path(plan,yaw,self.node.get_clock().now().to_msg(),self.settings.path_spacing_m)
            route = self.registry.route(list(plan.points), self.settings.max_start_distance_m)
            if set(route.nodes)&set(blocked_nodes) or set(route.edges)&set(blocked_edges): return None
            if route.nodes == request['route'].nodes and route.edges == request['route'].edges: return None
            # 후진/작업 방향 제약은 보존한다. 해당 경로를 일반 전진 우회로 치환하지 않는다.
            first = path.poses[0].pose
            if len(path.poses)>1:
                second = path.poses[1].pose.position
                heading = math.atan2(2*first.orientation.w*first.orientation.z,1-2*first.orientation.z**2)
                if (second.x-first.position.x)*math.cos(heading)+(second.y-first.position.y)*math.sin(heading)<-1e-6: return None
            return alternative
        except ValueError:
            return None

    def _query_abandoned(self, request: dict, context: Any) -> None:
        query = GetPassageState.Request(robot_id=self.robot_id, caller_boot_id=self.boot_id,
            target_boot_id=context.boot_id, request_id=context.request_id, permit_id=context.permit_id,
            target_server_epoch=context.server_epoch, query_id=self.ids.next('query'), timestamp=timestamp())
        future = self.get_client.call_async(query)
        def resolved(done: Any) -> None:
            with self.lock:
                try:
                    value = done.result()
                    if (value.query_id != query.query_id or not value.found or value.error_code != 'NONE'
                        or context_key(value.context) != context_key(context)
                        or value.context.permit_id != context.permit_id
                        or value.current_server_epoch != self.epoch):
                        raise RuntimeError('취소/발급 경합 조회 불일치')
                    if self.pending is request: self.pending = None
                    self._release_exited()
                except Exception as error:
                    self.fault = str(error)
                    self.node.get_logger().error(self.fault)
        future.add_done_callback(resolved)

    def _accepted(self, request: dict, future: Any) -> None:
        with self.lock:
            try:
                handle = future.result()
                request['handle'] = handle
                if not handle.accepted:
                    if self.pending is request: self.pending = None
                    return
                request['result_future'] = handle.get_result_async()
                request['result_future'].add_done_callback(lambda f:self._terminal(request,f))
                if request['abandoned'] or request['generation'] != self.generation:
                    request['abandoned'] = True
                    handle.cancel_goal_async()
            except Exception as error:
                self.fault = str(error)

    def _validate_grant(self, request: dict, response: Any) -> None:
        goal, result = request['goal'],response.result
        if (response.status != GoalStatus.STATUS_SUCCEEDED or result.result_code != 'GRANTED'
                or result.permission_state != 'ACTIVE' or result.error_code != 'NONE' or not result.context.permit_id
                or context_key(result.context) != context_key(goal.context)
                or list(result.granted_node_ids) != list(goal.route_node_ids)
                or list(result.granted_edge_ids) != list(goal.route_edge_ids)
                or result.stop_node_id != goal.stop_node_id or not result.allocated_zone_ids
                or any(z not in self.registry.zones for z in result.allocated_zone_ids)
                or not request['route'].hold.issubset(result.allocated_zone_ids)):
            raise RuntimeError('관제 허가가 원 요청·전체 경로·작업 공간과 일치하지 않습니다.')

    def _remember(self, request: dict, result: Any) -> dict:
        found = next((p for p in self.permits if p['context'].permit_id == result.context.permit_id),None)
        if found: return found
        permit = dict(context=deepcopy(result.context), task_id=request['goal'].task_id, zones=set(result.allocated_zone_ids), seen=set(),
                      sequence=0, hold=set(request['route'].hold), abandoned=request['abandoned'],
                      points=request['points'], cursor=0, future={})
        profile = self.registry.profile
        radius = math.hypot(profile['length_m']/2+profile['margin_each_side_m'],
                            profile['width_m']/2+profile['margin_each_side_m'])
        for i,(a,b) in enumerate(zip(permit['points'],permit['points'][1:])):
            for zid in permit['zones']:
                xmin,ymin,xmax,ymax = self.registry.zones[zid]['bounds_m']
                if (max(a[0],b[0])+radius >= xmin and min(a[0],b[0])-radius <= xmax
                    and max(a[1],b[1])+radius >= ymin and min(a[1],b[1])-radius <= ymax):
                    permit['future'][zid] = i+1
        permit['seen'].update(permit['zones'] & self.occupied)
        self.permits.append(permit)
        return permit

    def _terminal(self, request: dict, future: Any) -> None:
        with self.lock:
            if not request['abandoned'] or request.get('terminal_processed'):
                return
            request['terminal_processed'] = True
            try:
                response = future.result()
                if response.result.result_code == 'GRANTED':
                    self._validate_grant(request,response)
                    if response.result.context.server_epoch == self.epoch:
                        self._remember(request,response.result)['abandoned'] = True
                        self._query_abandoned(request,response.result.context)
                        return
                elif (response.result.result_code not in ('CANCELED','DENIED')
                      or response.result.context.permit_id or response.result.permission_state != 'NONE'
                      or context_key(response.result.context) != context_key(request['goal'].context)):
                    raise RuntimeError('교통 취소 결과 불명')
                if self.pending is request:
                    self.pending = None
                self._release_exited()
            except Exception as error:
                self.fault = '교통 요청 정리 필요: '+str(error)
                self.node.get_logger().error(self.fault)

    def wait_position_report(self, stamp_ns: int, check: Callable[[], None], timeout_s: float) -> None:
        """도착 이후 실제 Status 표본과 같은 허가 문맥의 Progress를 보낸 뒤 결과를 반환한다."""
        deadline = time.monotonic() + timeout_s
        while True:
            check()
            with self.lock:
                if not self.ready or self.fault:
                    raise RuntimeError('도착 위치 보고 중 교통 등록/위치 확인 불가')
                if self.pose_valid and self.latest_stamp >= stamp_ns:
                    self._report()
                    return
            if time.monotonic() >= deadline:
                raise TimeoutError('도착 이후 RobotStatus 표본 미수신')
            time.sleep(.02)

    def finish_task(self, task_id: str, timeout_s: float) -> None:
        """시험 소유권 반납 전 자신의 취소·미사용 예약 정리를 확인한다. 실제 점유는 유지한다."""
        deadline = time.monotonic() + timeout_s
        while True:
            with self.lock:
                request = self.pending
                own_pending = request is not None and request['goal'].task_id == task_id
                if own_pending:
                    request['abandoned'] = True
                    if request['handle'] is not None:
                        request['handle'].cancel_goal_async()
                    if request.get('result_future') is not None and request['result_future'].done():
                        self._terminal(request, request['result_future'])
                for permit in self.permits:
                    if permit.get('task_id') == task_id:
                        permit['abandoned'] = True
                self._release_exited()
                unused = any(p.get('task_id') == task_id and
                    (p['zones'] - self.occupied - (p['hold'] if p['hold'] & self.occupied else set()))
                    for p in self.permits)
                if not own_pending and not unused and self.release is None:
                    self._report()
                    return
                if self.fault or time.monotonic() >= deadline:
                    raise RuntimeError('교통 요청/반납 종료 미확인: ' + self.fault)
            time.sleep(.02)

    def movement_finished(self) -> None:
        with self.lock:
            self.moving = False
            self._stop()
            self._report()
            self._release_exited()

    def _release_exited(self) -> None:
        if self.release is not None or not self.ready or not self.pose_valid or not self.release_client.service_is_ready():
            return
        for permit in self.permits:
            if permit['context'].server_epoch != self.epoch:
                continue
            # 작업 구간 안에 있는 동안 전체 작업 예약을 유지한다.
            protected = permit['hold'] if permit['hold'] & self.occupied else set()
            if permit is self.current and self.moving:
                protected = protected | {z for z,index in permit['future'].items() if index >= permit['cursor']}
            zones = (permit['seen'] & permit['zones']) - self.occupied - protected
            mode = 'EXITED'
            if not zones and (permit['abandoned'] or permit is not self.current):
                zones = permit['zones'] - permit['seen'] - self.occupied - protected
                mode = 'UNUSED'
            if not zones: continue
            # 같은 위치에서 거절된 반납을 타이머로 반복하지 않는다.
            key = (self.latest_stamp, mode, tuple(sorted(zones)))
            if permit.get('last_attempt') == key: continue
            permit['last_attempt'] = key
            permit['sequence'] += 1
            self._report()
            req = ReleasePassage.Request(context=deepcopy(permit['context']), operation_sequence=permit['sequence'],
                release_zone_ids=sorted(zones), release_mode=mode, progress_sequence=self.progress_sequence, timestamp=timestamp())
            self.release = self.release_client.call_async(req)
            self.release.add_done_callback(lambda f,p=permit,r=req:self._released(p,r,f))
            return

    def _released(self, permit: dict, request: Any, future: Any) -> None:
        with self.lock:
            if future is not self.release:
                return
            self.release = None
            try:
                result = future.result()
                if (context_key(result.context) != context_key(request.context)
                    or result.context.permit_id != request.context.permit_id
                    or result.operation_sequence != request.operation_sequence
                    or result.current_server_epoch != self.epoch):
                    raise RuntimeError('반납 응답 식별자 불일치')
                if result.released:
                    if result.error_code != 'NONE' or set(result.released_zone_ids) != set(request.release_zone_ids):
                        raise RuntimeError('반납 전체 성공 응답 불일치')
                    permit['zones'] = set(result.remaining_zone_ids)
                    if result.permit_closed:
                        if permit['zones']: raise RuntimeError('종료 허가의 잔여 공간 불일치')
                        if permit in self.permits: self.permits.remove(permit)
                        if self.current is permit: self.current = None
            except Exception as error:
                self.fault = '교통 반납 확인 필요: '+str(error)
                self.node.get_logger().error(self.fault)

    def close(self) -> None:
        self._stop()
        self.node.destroy_timer(self.timer)
        self.acquire_client.destroy()
        self.ids.close()


def configure_traffic(node: Any, root: Path, profile: dict, settings: Any,
                      task_id: Callable[[],str]) -> TrafficClient | None:
    """환경이 명시적으로 선택한 경우만 활성화한다. 실물 기존 설정은 변경하지 않는다."""
    traffic = TrafficClient(node,root,profile,settings,task_id) if profile.get('traffic',{}).get('enabled',False) else None
    node._traffic = traffic
    return traffic
