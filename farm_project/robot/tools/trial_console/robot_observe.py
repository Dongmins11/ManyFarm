"""정지와 상태를 구독하여 관찰한다. 서비스·Action 요청 없음."""
import json
import time
import rclpy
from farm_interfaces.msg import RobotStatus
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.convert import message_to_ordereddict
rclpy.init(args=[]); node = rclpy.create_node('trial_console_status'); statuses=[]; odom=[]
node.create_subscription(RobotStatus, '/harvest_01/status', lambda m: statuses.append((time.monotonic(),m)), 10)
node.create_subscription(Odometry, '/harvest_01/odom', lambda m: odom.append((time.monotonic(),m)), qos_profile_sensor_data)
end=time.monotonic()+2.5
while time.monotonic()<end:
    rclpy.spin_once(node,timeout_sec=.1)
now=time.monotonic(); recent=[m for t,m in odom if now-t<1]
print(json.dumps(dict(status=message_to_ordereddict(statuses[-1][1]) if statuses and now-statuses[-1][0]<2 else None,
    odom_samples=len(recent), stopped=bool(len(recent)>=10 and all(abs(m.twist.twist.linear.x)+abs(m.twist.twist.angular.z)<1e-6 for m in recent))),ensure_ascii=False))
node.destroy_node();rclpy.shutdown()
