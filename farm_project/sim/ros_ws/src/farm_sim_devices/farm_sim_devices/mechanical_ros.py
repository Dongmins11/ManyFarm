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


class MechanicalRosServer:
    def __init__(self,node) -> None:
        self.node=node;self.lock=threading.RLock()
        self.session=None;self.proof=None;self.received=0.;self.lid_open=False;self.task=None;self.busy=False
        self.group=ReentrantCallbackGroup()
        self.publisher=node.create_publisher(TransportDeviceState,'devices/transport_state',qos_profile_sensor_data)
        self.proof_pub=node.create_publisher(String,'sim/basket_alignment',10)
        self.server=ActionServer(node,MechanicalOperation,'devices/mechanical_operation',self.execute,
            goal_callback=self.goal,cancel_callback=lambda _:CancelResponse.ACCEPT,callback_group=self.group)
        self.timer=node.create_timer(.1,self.publish,clock=Clock(clock_type=ClockType.STEADY_TIME),callback_group=self.group)

    def observe(self,session: str,proof: dict | None) -> None:
        with self.lock:
            if session!=self.session:
                self.session=session;self.lid_open=False;self.task=None;self.proof=None
            self.proof=proof;self.received=time.monotonic()

    def fresh(self) -> bool:
        if not isinstance(self.proof,dict) or time.monotonic()-self.received>.5:return False
        age=self.node.get_clock().now().nanoseconds/1e9-self.proof['sim_time_s']
        return 0<=age<=.5

    def ready(self) -> bool:
        return self.fresh() and self.proof.get('hold_pass') is True

    def publish(self) -> None:
        with self.lock:
            msg=TransportDeviceState();msg.header.stamp=self.node.get_clock().now().to_msg()
            msg.ready=self.fresh();msg.safe_to_clear=self.ready() and not self.lid_open
            msg.count_valid=False;msg.loaded_count=0;msg.estop=False
            self.publisher.publish(msg)
            self.proof_pub.publish(String(data=json.dumps(dict(session=self.session,proof=self.proof,
                fresh=self.fresh(),lid_open=self.lid_open,task_id=self.task,count_valid=False),ensure_ascii=False)))

    def goal(self,request) -> GoalResponse:
        with self.lock:
            if self.busy or not request.task_id or request.operation not in ('LID_OPEN','LID_CLOSE') or not self.ready():
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
                if self.goal_session!=self.session or not self.ready():
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
