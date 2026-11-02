"""바구니 정렬 평가에 근거한 가상 덮개 장치. 과실 수량/기구 물리를 위조하지 않는다."""
import json
import threading
import time
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock,ClockType
from rclpy.qos import qos_profile_sensor_data
from farm_interfaces.action import MechanicalOperation
from farm_interfaces.msg import TransportDeviceState
from std_msgs.msg import String
from std_srvs.srv import Trigger


class MechanicalRosServer:
    def __init__(self,node) -> None:
        self.node=node;self.lock=threading.RLock()
        self.proof_changed=threading.Condition(self.lock);self.waiting_for_hold=False;self.hold_cancelled=False
        self.session=None;self.proof=None;self.received=0.;self.lid_open=False;self.task=None;self.busy=False
        self.group=ReentrantCallbackGroup()
        self.publisher=node.create_publisher(TransportDeviceState,'devices/transport_state',qos_profile_sensor_data)
        self.proof_pub=node.create_publisher(String,'sim/basket_alignment',10)
        self.server=ActionServer(node,MechanicalOperation,'devices/mechanical_operation',self.execute,
            goal_callback=self.goal,cancel_callback=lambda _:CancelResponse.ACCEPT,callback_group=self.group)
        self.timer=node.create_timer(.1,self.publish,clock=Clock(clock_type=ClockType.STEADY_TIME),callback_group=self.group)
        # 실물 TriggerDevice 계약. Action과 동일한 정렬 증거·덮개 상태를 공유한다.
        self.services = [node.create_service(Trigger,'device/'+name,callback,callback_group=self.group)
            for name,callback in [('lid_open',self.open_lid),('lid_close',self.close_lid),
                                  ('stop',self.stop_device),('unload',self.unsupported_unload)]]

    def open_lid(self,request: Trigger.Request,response: Trigger.Response) -> Trigger.Response:
        return self.trigger_lid('LID_OPEN',response)

    def close_lid(self,request: Trigger.Request,response: Trigger.Response) -> Trigger.Response:
        return self.trigger_lid('LID_CLOSE',response)

    def trigger_lid(self,operation: str,response: Trigger.Response) -> Trigger.Response:
        """Trigger에는 task ID가 없으므로 Action 세션과 혼용하지 않는다."""
        with self.lock:
            owner='trigger_lid'
            settled=True
            if (operation=='LID_OPEN' and not self.busy and not self.lid_open
                    and not self.ready() and self.hold_pending()):
                settled=self.wait_for_hold()

            if (not settled or self.busy or not self.operation_ready(operation) or
                    (self.lid_open and self.task!=owner) or
                    (operation=='LID_CLOSE' and not self.lid_open)):
                response.success=False
                response.message='가상 덮개 조건 불충족: '+json.dumps(dict(
                    fresh=self.fresh(),session=self.session,settled=settled,
                    proof=self.proof),ensure_ascii=False)
                self.node.get_logger().warning('SIM_VIRTUAL_LID_REJECT '+json.dumps(dict(
                    operation=operation,busy=self.busy,fresh=self.fresh(),lid_open=self.lid_open,
                    task=self.task,proof=self.proof),ensure_ascii=False))
                return response
            self.lid_open=operation=='LID_OPEN'
            self.task=owner if self.lid_open else None
            response.success=True
            response.message='SIM_VIRTUAL_LID '+json.dumps(dict(operation=operation,
                coverage=self.proof['coverage'],count_valid=False))
            self.node.get_logger().info(response.message)
            return response

    def hold_pending(self) -> bool:
        """정렬·정지는 충족하고 연속 유지 시간만 부족한 경우다."""
        return (self.fresh() and all(self.proof.get(key) is True
                for key in ('aligned','wheel_stopped','world_stopped')))

    def wait_for_hold(self) -> bool:
        """잠금을 풀어 새 평가를 받되 현재 세션에서 최대 시뮬 2초만 기다린다."""
        session=self.session
        start=self.node.get_clock().now().nanoseconds/1e9
        self.busy=True;self.waiting_for_hold=True;self.hold_cancelled=False
        self.node.get_logger().info('SIM_VIRTUAL_LID_WAIT '+json.dumps(self.proof))
        try:
            while True:
                now=self.node.get_clock().now().nanoseconds/1e9
                if self.hold_cancelled or self.session!=session or not 0<=now-start<2.:
                    return False
                if not self.hold_pending():return False
                if self.ready():return True
                # 실제시간은 콜백 양보에만 사용하며 완료/제한시간은 시뮬 시계다.
                self.proof_changed.wait(timeout=.02)
        finally:
            self.busy=False;self.waiting_for_hold=False

    def stop_device(self,request: Trigger.Request,response: Trigger.Response) -> Trigger.Response:
        with self.lock:
            if self.waiting_for_hold:
                self.hold_cancelled=True;self.proof_changed.notify_all()
            # 순간 상태 전이만 존재한다. STOP은 자동 닫힘이나 수량 확인을 의미하지 않는다.
            response.success=(not self.busy or self.waiting_for_hold) and self.fresh()
            response.message='가상 기구 정지 확인' if response.success else '기구 작업/연결 확인 필요'
            return response

    def unsupported_unload(self,request: Trigger.Request,response: Trigger.Response) -> Trigger.Response:
        response.success=False
        response.message='선별장 실제 하역은 미구현; 수량·완료를 가정하지 않습니다.'
        return response

    def observe(self,session: str,proof: dict | None) -> None:
        with self.lock:
            if session!=self.session:
                self.session=session;self.lid_open=False;self.task=None;self.proof=None
            self.proof=proof;self.received=time.monotonic()
            self.proof_changed.notify_all()

    def fresh(self) -> bool:
        if not isinstance(self.proof,dict) or time.monotonic()-self.received>.5:return False
        age=self.node.get_clock().now().nanoseconds/1e9-self.proof['sim_time_s']
        return 0<=age<=.5

    def ready(self) -> bool:
        return self.fresh() and self.proof.get('hold_pass') is True

    def operation_ready(self,operation: str) -> bool:
        """열기는 인계 정렬, 닫기는 이미 열린 덮개와 현재 정지를 확인한다."""
        if operation=='LID_CLOSE':
            return (self.fresh() and self.lid_open and
                    self.proof.get('wheel_stopped') is True and self.proof.get('world_stopped') is True)
        return operation=='LID_OPEN' and self.ready()

    def publish(self) -> None:
        with self.lock:
            msg=TransportDeviceState();msg.header.stamp=self.node.get_clock().now().to_msg()
            msg.ready=self.fresh()
            msg.safe_to_clear=bool(self.fresh() and not self.lid_open and
                self.proof.get('wheel_stopped') is True and self.proof.get('world_stopped') is True)
            msg.count_valid=False;msg.loaded_count=0;msg.estop=False
            self.publisher.publish(msg)
            self.proof_pub.publish(String(data=json.dumps(dict(session=self.session,proof=self.proof,
                fresh=self.fresh(),lid_open=self.lid_open,task_id=self.task,count_valid=False),ensure_ascii=False)))

    def goal(self,request) -> GoalResponse:
        with self.lock:
            if self.busy or not request.task_id or not self.operation_ready(request.operation):
                return GoalResponse.REJECT
            if self.lid_open and request.task_id!=self.task:return GoalResponse.REJECT
            if request.operation=='LID_CLOSE' and (not self.lid_open or request.task_id!=self.task):return GoalResponse.REJECT
            self.busy=True;self.goal_session=self.session
            return GoalResponse.ACCEPT

    def execute(self,handle) -> MechanicalOperation.Result:
        with self.lock:
            result=MechanicalOperation.Result(count_valid=False,loaded_count=0)
            try:
                if handle.is_cancel_requested:
                    handle.canceled();result.error_message='가상 덮개 작업 취소';return result
                if self.goal_session!=self.session or not self.operation_ready(handle.request.operation):
                    handle.abort();result.error_message='바구니 정렬/정지 평가 만료';return result
                # 사용자 승인된 추상 장치 상태 전이. USD 덮개를 움직이거나 과실 수를 생성하지 않는다.
                self.lid_open=handle.request.operation=='LID_OPEN'
                self.task=handle.request.task_id if self.lid_open else None
                result.success=True;result.safe_to_clear=not self.lid_open
                self.node.get_logger().info('SIM_VIRTUAL_LID '+json.dumps(dict(task=handle.request.task_id,
                    operation=handle.request.operation,coverage=self.proof['coverage'],count_valid=False)))
                handle.succeed();return result
            finally:self.busy=False

    def close(self) -> None:
        self.timer.cancel();self.server.destroy()
        for service in self.services:self.node.destroy_service(service)
