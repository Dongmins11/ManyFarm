"""최종 cmd_vel 단일 발행자. 제어권 만료 시 영속적인 정지 출력을 보낸다."""
from farm_navigation.operation_clock import operation_time
import math
import time
import uuid
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from farm_interfaces.srv import MotionLease

class Lease:
    """ROS와 독립적인 소유권 판정. 현재 토큰만 갱신/해제할 수 있다."""
    def __init__(self, ttl=0.6):
        self.ttl, self.owner, self.token, self.deadline = ttl, '', '', 0.
        self.retired={}
        self.reason=''
        self.last_time=None
    def _observe_time(self, now):
        # 시뮬 reset 이전 제어권을 새 시각에서 재사용하지 않는다.
        if self.last_time is not None and now < self.last_time:
            if self.token:self.retired[self.owner]=self.token
            self.owner,self.token,self.deadline='','',0.
        self.last_time=now
    def request(self, owner, token, release, now):
        self._observe_time(now)
        self.reason=''
        if now >= self.deadline and self.token:
            self.retired[self.owner]=self.token
            self.owner,self.token,self.deadline='','',0.
        if owner not in ('nav','precision'):
            self.reason='INVALID_OWNER';return False,''
        if release:
            if token and self.retired.get(owner)==token:return True,''
            if (owner,token) != (self.owner,self.token) or not token:
                self.reason='TOKEN_MISMATCH';return False,''
            self.retired[owner]=token
            self.owner,self.token,self.deadline = '','',0.
            return True,''
        if token:
            if (owner,token) != (self.owner,self.token):
                self.reason='LEASE_EXPIRED' if self.retired.get(owner)==token else 'TOKEN_MISMATCH'
                return False,''
        elif self.owner:
            self.reason='OWNER_BUSY:'+self.owner
            return False,''
        else:
            self.owner,self.token = owner,uuid.uuid4().hex
        self.deadline = now+self.ttl
        return True,self.token
    def permits(self, owner, now):
        self._observe_time(now)
        return bool(self.token) and self.owner==owner and now<self.deadline

class MotionGate(Node):
    def __init__(self):
        super().__init__('motion_gate')
        self.lease=Lease()
        self.last_command=0.
        self.pub=self.create_publisher(Twist,'cmd_vel',10)
        self.create_subscription(Twist,'motion/nav',lambda m:self.command('nav',m),10)
        self.create_subscription(TwistStamped,'motion/precision',self.precision,10)
        self.create_service(MotionLease,'motion/lease',self.request)
        self.create_timer(.05,self.watchdog)
    def zero(self): self.pub.publish(Twist())
    def request(self, request, response):
        if not request.release and self.count_publishers(self.pub.topic_name)>1:
            response.accepted=False;response.error_message='최종 cmd_vel 중복 발행자 존재';return response
        if not request.release and self.get_clock().ros_time_is_active and operation_time(self)<=0.:
            response.accepted=False;response.error_message='CLOCK_NOT_READY';return response
        old=self.lease.token
        response.accepted,response.token=self.lease.request(request.owner,request.token,request.release,operation_time(self))
        response.error_message='' if response.accepted else self.lease.reason
        if old!=self.lease.token:
            self.last_command=0.;self.zero()
        return response
    def precision(self, msg):
        age=(self.get_clock().now().nanoseconds-msg.header.stamp.sec*10**9-msg.header.stamp.nanosec)/1e9
        if 0<=age<.25:self.command('precision',msg.twist)
    def command(self, owner, msg):
        now=operation_time(self)
        values=(msg.linear.x,msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y,msg.angular.z)
        if self.lease.permits(owner,now) and all(map(math.isfinite,values)):
            self.last_command=now;self.pub.publish(msg)
    def watchdog(self):
        self.lease._observe_time(operation_time(self))
        if self.count_publishers(self.pub.topic_name)>1:self.lease.deadline=0.
        if operation_time(self)>=self.lease.deadline or operation_time(self)-self.last_command>.25:self.zero()

def main(args=None):
    rclpy.init(args=args); node=MotionGate()
    try:rclpy.spin(node)
    finally:node.zero();node.destroy_node();rclpy.try_shutdown()
