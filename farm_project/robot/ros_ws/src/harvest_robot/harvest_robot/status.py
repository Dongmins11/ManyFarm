"""수확 이동 및 인계 상태를 1 Hz로 보고한다. 동작 명령은 보내지 않는다."""
from datetime import datetime, timezone
import math
import time
import uuid
from rclpy.clock import Clock, ClockType
from rclpy.time import Time
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import Buffer, TransformListener
from nav2_msgs.action import FollowPath
from sensor_msgs.msg import BatteryState
from farm_interfaces.msg import RobotStatus


class HarvestStatus:
    """환경 설정에서 선택적으로 활성화한다. 타이머는 주행 명령을 보내지 않는다."""
    def __init__(self, node, settings, config: dict) -> None:
        self.node, self.settings, self.config = node, settings, config
        self.traffic = getattr(node, '_traffic', None)
        self.boot_id = self.traffic.boot_id if self.traffic is not None else uuid.uuid4().hex
        self.sequence = 0
        self.battery = None
        self.group = MutuallyExclusiveCallbackGroup()
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, node)
        self.client = ActionClient(node, FollowPath, settings.follow_action, callback_group=self.group)
        self.publisher = node.create_publisher(RobotStatus, 'status', 10)
        self.subscription = node.create_subscription(BatteryState, config['battery_topic'],
            self.on_battery, qos_profile_sensor_data, callback_group=self.group)
        self.clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.timer = node.create_timer(1.0, self.publish, callback_group=self.group, clock=self.clock)

    def on_battery(self, msg) -> None:
        """BatteryState.percentage는0–1. 전압에서 잔량을 추측하지 않는다."""
        value = float(msg.percentage)
        self.battery = (100.0*value, time.monotonic()) if math.isfinite(value) and 0 <= value <= 1 else None

    def publish(self) -> None:
        node = self.node
        status = RobotStatus()
        status.robot_id = node.config['robot_id']
        status.map_id = self.config['map_id']
        status.boot_id = self.boot_id
        self.sequence += 1
        status.sequence = self.sequence
        status.timestamp = datetime.now(timezone.utc).isoformat()
        transfer = (node.transfer.snapshot() if node.transfer is not None else
                    dict(task_id='', phase='', loaded_count=None, transfer_required=False, error=''))
        status.transfer_required = transfer['transfer_required']
        status.loaded_count = transfer['loaded_count'] if transfer['loaded_count'] is not None else 0
        status.pose.frame_id = self.settings.map_frame
        with node.lock:
            busy, blocked, stopping = node.busy, node.blocked, node.stopping
            goal = node.active_goal
            arm_stage = busy and getattr(node, 'mission_stage', '') == 'ARM'
            status.current_task_id = (transfer['task_id'] or
                                      (goal.request.harvest_task.task_id if goal is not None else ''))
        current = node.handoff.current
        if current is not None:
            busy = True
            status.current_task_id = current[1]
        status.state = ('ERROR' if blocked else transfer['phase'] or
                        ('RETURNING' if current and current[0] == 'return' else 'HARVESTING' if arm_stage else 'NAVIGATION_MOVE' if busy else 'IDLE'))
        status.ready = False
        errors = []
        if blocked:
            if not getattr(node, 'arm_travel_ready', True):
                errors.append(('ARM_TRAVEL_NOT_READY', '팔 작업 중단 후 접힘 확인 필요'))
            else:
                errors.append((transfer['error'] or 'CANCEL_UNCONFIRMED', '이전 동작 또는 인계 복구 확인 필요'))
        if node.transfer is not None and node.transfer.load_topic and transfer['loaded_count'] is None:
            errors.append(('LOAD_UNAVAILABLE', 'loaded_count=0은 미측정 자리값; 빈 적재함 확인 아님'))
        arm = getattr(node, 'arm_client', None)
        arm_ready = arm is None or arm.server_is_ready()
        if not arm_ready:
            errors.append(('ARM_NOT_READY', '팔 Action 서버 연결 대기'))
        if stopping: errors.append(('SHUTDOWN', '서버 종료 중'))
        stamp = 0
        try:
            tf = self.buffer.lookup_transform(self.settings.map_frame, self.settings.base_frame, Time())
            stamp = tf.header.stamp.sec*10**9 + tf.header.stamp.nanosec
            age = (node.get_clock().now().nanoseconds-stamp)/1e9
            if stamp == 0 or not 0 <= age <= self.settings.tf_max_age_s:
                raise ValueError('위치 TF 시각 만료')
            t, q = tf.transform.translation, tf.transform.rotation
            norm = math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)
            if not math.isfinite(norm) or norm < 1e-9: raise ValueError('잘못된 TF 회전')
            x,y,z,w = q.x/norm,q.y/norm,q.z/norm,q.w/norm
            values = (t.x,t.y,t.z,math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)))
            if not all(math.isfinite(v) for v in values): raise ValueError('잘못된 TF 위치')
            status.pose.position.x,status.pose.position.y,status.pose.position.z,status.pose.yaw = values
            status.ready = not (busy or blocked or stopping) and arm_ready and self.client.server_is_ready()
            if not self.client.server_is_ready():errors.append(('NAV_NOT_READY','FollowPath 서버 연결 대기'))
        except Exception as error:
            # 유효하지 않은 위치를 정상값으로 표시하지 않는다. 주행은 기존 미션이 판단한다.
            errors.append(('POSE_UNAVAILABLE',str(error)))
        if self.battery is not None and time.monotonic()-self.battery[1] <= 5.0:
            status.battery_percent = self.battery[0]
        else:
            # float 필드에 unknown 규약이 없으므로 오류와 함께 자리값을 명시한다.
            status.battery_percent = 0.0
            errors.append(('BATTERY_UNAVAILABLE','battery_percent=0은 미측정 자리값; 잔량0% 측정 아님'))
        status.error_code = errors[0][0] if errors else 'NONE'
        status.error_message = '; '.join(code+': '+message for code,message in errors)
        self.publisher.publish(status)
        if self.traffic is not None:
            self.traffic.on_status(status, stamp)

    def close(self) -> None:
        self.node.destroy_timer(self.timer)
        self.listener.unregister()
        self.client.destroy()
