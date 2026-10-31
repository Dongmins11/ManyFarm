"""ROS Action 접수/예약/취소/최종 응답. 업무 진행은 Controller가 담당한다."""
from farm_navigation.operation_clock import operation_time
from concurrent.futures import Future
from datetime import datetime
from threading import Lock
from typing import Any
import math
import re
import time
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from farm_interfaces.action import ReturnToStation, CheckRoute, TransportPickup, BucketUnload
from std_srvs.srv import SetBool
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data
from farm_interfaces.srv import TransferEvent, UnloadEvent
from .configuration import destination, validate_precision, validate_unload_workflow
from .mission_types import Request, Outcome, utc


class TransportCommunication:
    def __init__(self, node: Any) -> None:
        self._node = node
        self._lock = Lock()
        self._reservation = None
        self._pending = None
        self._active = None
        self._completion = None
        self._servers = []
        for action, name, kind in [(ReturnToStation,'return_to_station','return'),
                                   (CheckRoute,'internal/check_route','route'),
                                   (TransportPickup,'transport_pickup','pickup'),
                                   (BucketUnload,'bucket_unload','unload')]:
            self._servers.append(ActionServer(node,action,name,
                goal_callback=lambda goal,k=kind:self._goal(goal,k),
                handle_accepted_callback=self._accepted,
                cancel_callback=self._cancel,execute_callback=self._execute,
                callback_group=node.callbacks))

        self._reset_odom_at=0.
        self._reset_stationary_since=None
        self._reset_stamp=None
        self._reset_sub=node.create_subscription(Odometry,'odom',self._recovery_odom,
            qos_profile_sensor_data,callback_group=node.callbacks)
        self._reset_service=node.create_service(SetBool,'recovery_reset',self._recovery_reset,
            callback_group=node.callbacks)
        self._transfer_service=node.create_service(TransferEvent,'transfer_event',self._event,callback_group=node.callbacks)
        self._unload_service=node.create_service(UnloadEvent,'unload_event',self._unload_event,callback_group=node.callbacks)

    def _recovery_odom(self, message):
        now=operation_time(self._node)
        stamp=message.header.stamp.sec*1e9+message.header.stamp.nanosec
        age=(self._node.get_clock().now().nanoseconds-stamp)/1e9
        v=message.twist.twist
        values=(v.linear.x,v.linear.y,v.linear.z,v.angular.x,v.angular.y,v.angular.z)
        with self._lock:
            valid=(0<=age<=.5 and all(math.isfinite(x) for x in values)
                and (self._reset_stamp is None or stamp>self._reset_stamp))
            stationary=valid and all(abs(x)<.005 for x in values[:3]) and all(abs(x)<.02 for x in values[3:])
            if not stationary or now-self._reset_odom_at>.5:self._reset_stationary_since=None
            if stationary and self._reset_stationary_since is None:self._reset_stationary_since=now
            self._reset_odom_at=now if valid else 0.
            self._reset_stamp=stamp

    def _recovery_reset(self, request, response):
        # Goal 예약과 동일 lock으로 새 명령 접수와 복구를 직렬화한다.
        with self._lock:
            c=self._node.controller
            try:
                if not request.data:raise ValueError('로봇을 도킹 구역 밖으로 옮겼다는 운영자 확인(data=true)이 필요합니다.')
                if self._node.stopping or self._reservation is not None or c.busy:
                    raise ValueError('실행 중인 작업/종료 처리 중에는 복구할 수 없습니다.')
                now=operation_time(self._node)
                if (now-self._reset_odom_at>.5 or self._reset_stationary_since is None
                        or now-self._reset_stationary_since<1.):
                    raise ValueError('최신 odom으로 1초 이상 정지를 확인해야 합니다.')
                device = self._node.device
                if hasattr(device, 'recovery_ready'):
                    if not device.recovery_ready(): raise ValueError('하역 서비스가 아직 실행 중입니다.')
                elif device.available():
                    raise ValueError('기구 연결 상태는 별도 해제 확인이 필요합니다.')
                if self._node.docking.pending:
                    # 결과 대기 중 시간이 흘러도 과거 정지 표본을 재사용하지 않는다.
                    self._node.docking.stop(stationary_confirmed=lambda:
                        operation_time(self._node)-self._reset_odom_at<=.5
                        and self._reset_stationary_since is not None
                        and operation_time(self._node)-self._reset_stationary_since>=1.)
                if self._node.lease is not None and self._node.lease.token:
                    raise ValueError('주행 제어권이 남아 있습니다.')
                self._node.mission.operator_reset()
                if hasattr(device, 'operator_reset'): device.operator_reset()
                c.parked_request = None
                c.docked_request=None
                c.last_outcome=None
                c.blocked=False
                response.success=True
                response.message='수동 복구 완료. 자동 이동하지 않습니다. 새 명령을 요청하세요.'
                self._node.get_logger().warning(response.message)
            except Exception as exc:
                response.success=False;response.message=str(exc)
            return response

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._reservation is not None

    def _goal(self, goal: Any, kind: str) -> GoalResponse:
        with self._lock:
            try:
                if self._reservation is not None or self._node.stopping or self._node.controller.blocked:
                    raise ValueError('ROBOT_BUSY/RECOVERY_REQUIRED')
                docked=self._node.controller.docked_request
                if docked is not None and not self._node.profile.get('precision_registry',{}).get('profiles',{}).get(docked.profile_id,{}).get('clearance_corridor_verified'):
                    raise ValueError('DOCKED: 도킹 해제 미구현/미검증. 새 이동을 시작할 수 없습니다.')
                if goal.robot_id != self._node.profile['robot_id'] or goal.map_id != self._node.profile['map_id']:
                    raise ValueError('robot_id/map_id 불일치')
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',goal.task_id):
                    raise ValueError('task_id 형식 오류')
                stamp = datetime.fromisoformat(goal.timestamp)
                if stamp.tzinfo is None:
                    raise ValueError('timestamp 시간대 필요')
                if goal.task_id in self._node.mission.records:
                    raise ValueError('기존 task_id 재실행 금지')
                trial = self._node.profile.get('sorter_dock_trial', {})
                dock_only_trial = (kind == 'unload' and trial.get('enabled') is True
                                   and goal.station_id == trial.get('station_id'))
                profile_id='';clearance_xy=None;clearance_yaw=None;entry_stage=False
                transfer_id='';harvest_robot_id='';target_marker_id=-1;docking_marker_id=-1
                navigation_return = (kind == 'return'
                    and self._node.profile.get('station_return_mode') == 'navigation_only')
                if navigation_return:
                    xy,yaw = destination(self._node.profile,self._node.graph,goal.station_id)
                    station = goal.station_id
                elif kind in ('return','unload'):
                    if not self._node.docking.available():
                        raise ValueError('ROBOT_NOT_READY: 정밀 도킹 미연결. internal/check_route로 이동만 점검하세요.')
                    xy,yaw = destination(self._node.profile,self._node.graph,goal.station_id)
                    station = goal.station_id
                    item=self._node.profile['registry']['destinations'][station]
                    profile_id=item['docking_profile']
                    entry_stage=kind=='return' and 'entry_node_id' in item
                    clearance_node=item.get('observation_node_id') if entry_stage else item.get('clearance_node_id')
                    clearance_yaw=yaw if entry_stage else item.get('clearance_yaw_rad')
                    if entry_stage:
                        precision=self._node.profile['precision_registry']['profiles'][profile_id]
                        target_marker_id=precision['target_marker_id'];docking_marker_id=precision['docking_marker_id']
                    if clearance_node not in self._node.graph.nodes or isinstance(clearance_yaw,bool) or not isinstance(clearance_yaw,(int,float)) or not math.isfinite(clearance_yaw):
                        raise ValueError('이격점/방향 미확정')
                    clearance_xy=self._node.graph.nodes[clearance_node]
                    if kind=='unload':
                        if not dock_only_trial and not self._node.device.available():raise ValueError('하역 기구 브릿지 미연결')
                elif kind=='pickup':
                    if self._node.profile.get('pickup_workflow'):
                        from .pickup_workflow import validate_pickup_workflow
                        workflow = validate_pickup_workflow(self._node.profile, self._node.device)
                        if (goal.target_marker_id, goal.docking_marker_id) != (workflow['initial_marker_id'], workflow['final_marker_id']):
                            raise ValueError('인계 마커 역할: 1차/최종 ID 불일치')
                    elif not getattr(self._node.device, 'supports', lambda op: True)('CONFIRM_RECEIPT'):
                        raise ValueError('수령/수량 검증 장치 미연결: 현재 Trigger 연결은 하역 전용')
                    if not self._node.docking.available() or not self._node.device.available():
                        raise ValueError('정밀주행/수령 브릿지 미연결')
                    pose=goal.staging_pose
                    xy,yaw=(pose.position.x,pose.position.y),pose.yaw
                    if pose.frame_id!=self._node.settings.map_frame or not math.isfinite(pose.position.z) or abs(pose.position.z)>1e-6 or not all(math.isfinite(v) for v in (*xy,yaw)):
                        raise ValueError('유한한 map 평면 staging_pose 필요')
                    self._node.graph._candidates(xy,self._node.settings.max_goal_distance_m)
                    if not all(re.fullmatch(r'[A-Za-z0-9_-]{1,128}',v) for v in (goal.transfer_id,goal.harvest_robot_id)):
                        raise ValueError('인계/상대 ID 형식 오류')
                    station='';profile_id=self._node.profile.get('pickup_profile','harvest')
                    transfer_id,harvest_robot_id=goal.transfer_id,goal.harvest_robot_id
                    target_marker_id,docking_marker_id=goal.target_marker_id,goal.docking_marker_id
                    if min(target_marker_id,docking_marker_id)<0:raise ValueError('마커 ID 필요')
                    clearance_xy,clearance_yaw=xy,yaw
                else:
                    if not self._node.get_parameter('allow_route_checks').value:
                        raise ValueError('내부 주행 시험 비활성')
                    pose = goal.goal_pose
                    xy,yaw = (pose.position.x,pose.position.y),pose.yaw
                    if pose.frame_id != self._node.settings.map_frame or not math.isfinite(pose.position.z) or abs(pose.position.z)>1e-6:
                        raise ValueError('map 평면 좌표 필요')
                    if not all(math.isfinite(v) for v in (*xy,yaw)):
                        raise ValueError('유한한 XY/yaw 필요')
                    self._node.graph._candidates(xy,self._node.settings.max_goal_distance_m)
                    station = ''
                integrated_clearance = kind == 'unload' and not dock_only_trial and validate_unload_workflow(self._node.profile, station)
                if kind != 'route' and not navigation_return and not (kind == 'pickup' and self._node.profile.get('pickup_workflow')):validate_precision(self._node.profile,profile_id,target_marker_id,docking_marker_id,require_clearance=not (dock_only_trial or entry_stage or integrated_clearance))
                if not self._node.route_ready():
                    raise ValueError('ROBOT_NOT_READY: 최신 TF/odom/scan 및 정지 필요')
                self._reservation = Request(goal.task_id,kind,xy,yaw,station,transfer_id,harvest_robot_id,target_marker_id,docking_marker_id,profile_id,clearance_xy,clearance_yaw,dock_only_trial,entry_stage)
                if dock_only_trial:
                    self._node.get_logger().warning('DOCK_ONLY_TRIAL: UNLOAD_READY 가정, 실제 하역/자동 이탈 없음. 도킹 후 취소까지 대기.')
                return GoalResponse.ACCEPT
            except Exception as exc:
                self._node.get_logger().warning('Goal 거절: '+str(exc))
                return GoalResponse.REJECT

    def _accepted(self, handle: Any) -> None:
        with self._lock:
            self._active = handle
            self._completion = Future()
            self._pending = (self._reservation,handle,self._completion)
        handle.execute()

    def _cancel(self, handle: Any) -> CancelResponse:
        with self._lock:
            if handle is not self._active:
                return CancelResponse.REJECT
            self._node.controller.cancel()
            return CancelResponse.ACCEPT

    def update(self) -> None:
        # 이 메서드는 Node의 단일 Controller timer에서만 실행한다.
        with self._lock:
            pending,self._pending = self._pending,None
        if pending:
            request,handle,completion = pending
            try:
                future = self._node.controller.start(request,lambda phase:self._feedback(handle,request,phase))
                future.add_done_callback(lambda done:completion.set_result(done.result()))
            except Exception as exc:
                self._node.controller.blocked = True
                completion.set_result(Outcome('FAILED','INTERNAL_ERROR',str(exc)))
        if self._node.stopping or (self._active and self._active.is_cancel_requested):
            self._node.controller.cancel()
        self._node.controller.update()

    def _event(self, request, response):
        try:
            if not self._node.controller.busy or self._node.stopping:
                raise ValueError('활성 작업 없음/종료 중')
            self._node.controller.check()
            stamp=datetime.fromisoformat(request.timestamp)
            if stamp.tzinfo is None or request.robot_id!=self._node.profile['robot_id']:
                raise ValueError('robot_id/timestamp 오류')
            self._node.controller.transfer.accept(request.task_id,request.transfer_id,request.source_robot_id,request.event)
            response.accepted=True;response.error_code='NONE'
        except Exception as exc:
            response.accepted=False;response.error_code='INVALID_EVENT';response.error_message=str(exc)
        response.timestamp=utc()
        return response

    def _unload_event(self, request: Any, response: Any) -> Any:
        try:
            stamp=datetime.fromisoformat(request.timestamp)
            if stamp.tzinfo is None or request.robot_id!=self._node.profile['robot_id']:
                raise ValueError('robot_id/timestamp 오류')
            if not self._node.controller.busy or self._node.stopping:
                raise ValueError('활성 작업 없음/종료 중')
            self._node.controller.check()
            self._node.controller.unload.accept(request.task_id,request.station_id,request.event)
            response.accepted=True;response.error_code='NONE';response.error_message=''
        except Exception as exc:
            response.accepted=False;response.error_code='INVALID_EVENT';response.error_message=str(exc)
        response.timestamp=utc()
        return response

    @staticmethod
    def _action(kind):
        return {'return':ReturnToStation,'route':CheckRoute,'pickup':TransportPickup,'unload':BucketUnload}[kind]

    def _feedback(self, handle: Any, request: Request, phase: str) -> None:
        message=self._action(request.kind).Feedback()
        message.task_id,message.timestamp=request.task_id,utc()
        if request.kind in ('return','route'):message.phase=phase
        else:message.event=phase
        if request.kind!='route':message.robot_id=self._node.profile['robot_id']
        if request.kind in ('return','unload'):message.station_id=request.station_id
        if request.kind=='return':message.docked=False
        if request.kind=='pickup':message.transfer_id=request.transfer_id
        if request.kind=='unload':message.progress_ratio={'MOVING_STARTED':0.,'WAITING_FOR_UNLOAD':.2,'DOCKING_STARTED':.3,'UNLOADING_STARTED':.6,'CLEARING_STARTED':.9}.get(phase,0.)
        handle.publish_feedback(message)

    def _execute(self, handle: Any) -> Any:
        with self._lock:
            completion,request = self._completion,self._reservation
        while not completion.done():
            time.sleep(.02)
        outcome = completion.result()
        if outcome.result_code == 'CANCELED' and not handle.is_cancel_requested:
            outcome = Outcome('FAILED','INTERRUPTED',outcome.error_message or '서버 종료/내부 중단')
        result = self._action(request.kind).Result()
        result.task_id = request.task_id
        result.result_code,result.error_code,result.error_message = outcome.result_code,outcome.error_code,outcome.error_message
        result.timestamp = utc()
        if request.kind != 'route':result.robot_id=self._node.profile['robot_id']
        if request.kind in ('return','unload'):result.station_id=request.station_id
        if request.kind=='return':result.docked=outcome.docked
        elif request.kind=='pickup':result.transfer_id=request.transfer_id
        elif request.kind=='route':result.arrived=outcome.arrived
        if outcome.result_code == 'SUCCESS':
            handle.succeed()
        elif outcome.result_code == 'CANCELED' and handle.is_cancel_requested:
            handle.canceled()
        else:
            handle.abort()
        with self._lock:
            self._reservation,self._active,self._completion = None,None,None
        return result

    def close(self) -> None:
        self._node.destroy_service(self._transfer_service)
        self._node.destroy_service(self._unload_service)
        for server in self._servers:
            server.destroy()
