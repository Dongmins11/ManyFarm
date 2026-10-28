"""예찰의 업무 상태와 실제 TF를 기존 RobotStatus 형식으로 발행한다."""
from datetime import datetime, timezone
import math
from rclpy.clock import Clock, ClockType
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from farm_interfaces.msg import RobotStatus


class ScoutTrafficStatus:
    def __init__(self, node) -> None:
        self.node = node
        self.sequence = 0
        self.publisher = node.create_publisher(RobotStatus, 'status', 10)
        self.timer = node.create_timer(1., self.publish, callback_group=MutuallyExclusiveCallbackGroup(),
                                      clock=Clock(clock_type=ClockType.STEADY_TIME))

    def publish(self) -> None:
        node = self.node
        self.sequence += 1
        msg = RobotStatus(robot_id=node._cfg['robot_id'], boot_id=node._traffic.boot_id,
                          sequence=self.sequence, map_id=node._cfg['map_id'],
                          timestamp=datetime.now(timezone.utc).isoformat())
        msg.state = 'ERROR' if node._motion_uncertain else 'SCOUTING' if node._busy else 'IDLE'
        msg.ready = not (node._busy or node._motion_uncertain or node._shutdown_requested or node._readiness_error)
        msg.pose.frame_id = node._navigation_settings.map_frame
        goal = node._active_goal
        if goal is not None:
            msg.current_task_id = goal.request.task_id
        current = node._handoff.current
        if current is not None:
            msg.current_task_id = current[1]
            msg.ready = False
            if current[0] == 'traffic_test':
                msg.state = 'NAVIGATION_MOVE'
        msg.error_code = 'BATTERY_UNAVAILABLE'
        msg.error_message = 'BATTERY_UNAVAILABLE: battery_percent=0은 미측정 자리값'
        stamp = 0
        try:
            tf = node._poses.latest_sample()
            stamp = tf.header.stamp.sec*10**9+tf.header.stamp.nanosec
            age = (node.get_clock().now().nanoseconds-stamp)/1e9
            if not stamp or not 0 <= age <= node._navigation_settings.tf_max_age_s:
                raise ValueError('위치 TF 시각 만료')
            q,t = tf.transform.rotation,tf.transform.translation
            norm = math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)
            if norm < 1e-9 or not math.isfinite(norm): raise ValueError('TF 회전 오류')
            x,y,z,w = q.x/norm,q.y/norm,q.z/norm,q.w/norm
            yaw = math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
            if not all(map(math.isfinite,(t.x,t.y,t.z,yaw))): raise ValueError('TF 좌표 오류')
            msg.pose.position.x,msg.pose.position.y,msg.pose.position.z = t.x,t.y,t.z
            msg.pose.yaw = yaw
        except Exception as error:
            msg.ready = False
            msg.error_code = 'POSE_UNAVAILABLE'
            msg.error_message += '; POSE_UNAVAILABLE: '+str(error)
        self.publisher.publish(msg)
        node._traffic.on_status(msg,stamp)
