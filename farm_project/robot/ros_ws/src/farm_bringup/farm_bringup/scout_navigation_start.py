"""Start real scout navigation only after localization provides a fresh TF."""
import time
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener, TransformException
from nav2_msgs.srv import ManageLifecycleNodes


class NavigationStart(Node):
    def __init__(self):
        super().__init__('scout_navigation_start')
        self.map_frame = self.declare_parameter('map_frame', 'map').value
        self.base_frame = self.declare_parameter('base_frame', 'base_link').value
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.manager = self.create_client(ManageLifecycleNodes,
                                         'lifecycle_manager_navigation/manage_nodes')

    def ready(self):
        try:
            tf = self.buffer.lookup_transform(self.map_frame, self.base_frame, Time())
            age = (self.get_clock().now() - Time.from_msg(tf.header.stamp)).nanoseconds / 1e9
            return 0.0 <= age <= 1.0
        except TransformException:
            return False

    def command(self, command):
        request = ManageLifecycleNodes.Request()
        request.command = command
        future = self.manager.call_async(request)
        # Do not issue overlapping STARTUP/RESET requests on a slow response.
        while rclpy.ok() and not future.done():
            rclpy.spin_once(self, timeout_sec=.1)
        if not rclpy.ok():
            return False
        result = future.result()
        return result is not None and result.success

    def run(self):
        next_log = 0.0
        reset_needed = False
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=.1)
            if not self.manager.service_is_ready():
                continue
            if reset_needed:
                if not self.command(ManageLifecycleNodes.Request.RESET):
                    self.get_logger().error('Navigation reset failed; startup retry stopped')
                    return
                reset_needed = False
            if not self.ready():
                if time.monotonic() >= next_log:
                    self.get_logger().info('NAV2_START_WAIT: 초기위치/최신 TF 대기; init 후 자동 활성화')
                    next_log = time.monotonic() + 5.0
                continue
            self.get_logger().info('Localization TF ready; activating navigation nodes')
            if self.command(ManageLifecycleNodes.Request.STARTUP):
                self.get_logger().info('NAV2_START_READY: 주행 노드 활성화 완료')
                return
            if rclpy.ok():
                self.get_logger().warning('Navigation startup failed; reset then wait for TF and retry')
                reset_needed = True
                # Bound retry rate for non-TF startup failures, while still processing TF.
                until = time.monotonic() + 5.0
                while rclpy.ok() and time.monotonic() < until:
                    rclpy.spin_once(self, timeout_sec=.1)


def main(args=None):
    rclpy.init(args=args)
    node = NavigationStart()
    try:
        node.run()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
