"""Isaac fleet의 시계만 ROS에 연결합니다. 로봇 서버/어댑터 재시작과 독립입니다."""
import json
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rosgraph_msgs.msg import Clock as ClockMessage
from farm_sim_devices.wire import LocalDatagrams


class ClockRelay(Node):
    def __init__(self) -> None:
        super().__init__('isaac_clock')
        self.declare_parameter('fleet_config', '')
        config = json.loads(Path(self.get_parameter('fleet_config').value).read_text())['clock']
        self.transport = LocalDatagrams(config['telemetry_port'], config['command_port'])
        self.publisher = self.create_publisher(ClockMessage, '/clock', 10)
        self.session, self.last = None, -1
        self.timer = self.create_timer(.005, self.poll, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def poll(self) -> None:
        for packet in self.transport.receive():
            if packet.get('kind') != 'clock' or not 0 <= time.monotonic()-packet.get('sent',0) <= 1:
                continue
            stamp, session = packet.get('stamp_ns'), packet.get('session')
            if not isinstance(stamp, int) or stamp < 0 or not isinstance(session,str): continue
            if self.session is not None and session != self.session:
                raise RuntimeError('Isaac 세션 변경. 로봇 Nav2/서버도 재시작하세요.')
            if stamp <= self.last: continue
            self.session, self.last = session, stamp
            message = ClockMessage()
            message.clock.sec, message.clock.nanosec = divmod(stamp, 1000000000)
            self.publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ClockRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.transport.close()
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
