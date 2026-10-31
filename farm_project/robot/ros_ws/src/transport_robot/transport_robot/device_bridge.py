"""기구 브릿지 Action 어댑터. 실제 펌웨어 구현은 이 계약 뒤에 연결한다."""
from farm_navigation.operation_clock import operation_time
import time
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from farm_interfaces.action import MechanicalOperation
from farm_interfaces.msg import TransportDeviceState
from farm_docking.clients import wait, accepted_goal

class DeviceBridge:
    def __init__(self,node,group):
        self.node=node;self.state=None;self.received=0.;self.handle=None
        self.client=ActionClient(node,MechanicalOperation,'devices/mechanical_operation',callback_group=group)
        self.sub=node.create_subscription(TransportDeviceState,'devices/transport_state',self.observe,qos_profile_sensor_data,callback_group=group)
    def observe(self,msg):
        age=(self.node.get_clock().now().nanoseconds-msg.header.stamp.sec*10**9-msg.header.stamp.nanosec)/1e9
        if 0<=age<1.:
            self.state=msg;self.received=operation_time(self.node)
    def available(self):
        return bool(self.state and operation_time(self.node)-self.received<1. and self.state.ready and not self.state.estop and self.client.server_is_ready())
    def run(self,request,operation,check):
        if not self.available():raise RuntimeError('기구 준비 상태 없음')
        q=MechanicalOperation.Goal();q.task_id=request.task_id;q.operation=operation
        self.handle=accepted_goal(self.client,q,clock=lambda: operation_time(self.node))
        if not self.handle.accepted:self.handle=None;raise RuntimeError('기구 명령 거절')
        future=self.handle.get_result_async();deadline=operation_time(self.node)+60.
        try:
            while not future.done():
                check()
                if not self.available():raise RuntimeError('기구 상태 단절/비상정지')
                if operation_time(self.node)>deadline:raise TimeoutError('기구 작업 시간 초과')
                time.sleep(.02)
            result=future.result()
            if result.status!=4:raise RuntimeError(result.result.error_message or '기구 작업 실패')
            return result.result
        except BaseException:
            wait(self.handle.cancel_goal_async(),3.,clock=lambda: operation_time(self.node));wait(future,5.,clock=lambda: operation_time(self.node));raise
        finally:self.handle=None
    def stop(self):
        if self.handle:wait(self.handle.cancel_goal_async(),3.,clock=lambda: operation_time(self.node))
