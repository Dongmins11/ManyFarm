"""구독 전용 시각 기록. 원본 stamp와 로봇 수신 시각을 보존하며 제어 명령은 없다."""
from pathlib import Path
import argparse
import json
import signal
import time


def process_snapshot() -> list[dict]:
    """태그/카메라 및 위치 추정 프로세스 argv를 읽는다. 프로세스를 변경하지 않는다."""
    rows = []
    for item in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = item.read_bytes().replace(b'\0', b' ').decode()
        except (OSError, UnicodeError):
            continue
        if any(word in argv for word in ('tag_capture', 'tag_amcl', 'apriltag',
                                        'camera_adapter', 'amcl', 'robot_state_publisher')):
            rows.append(dict(pid=int(item.parent.name), argv=argv))
    return rows


def main() -> None:
    """출력 파일을 받는다. age는 전송 지연뿐 아니라 송신 측 시각 부여도 포함한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from nav_msgs.msg import Odometry
    from tf2_msgs.msg import TFMessage
    rclpy.init(args=[])
    node = rclpy.create_node('station_return_timing_capture')
    stop = False
    def request_stop(signum: int, frame: object) -> None:
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    previous = {}
    with args.output.open('w', buffering=1) as output:
        def write(value: dict) -> None:
            output.write(json.dumps(value, ensure_ascii=False)+'\n')
        def receive(kind: str, stamp: object, parent: str, child: str) -> None:
            now = node.get_clock().now().nanoseconds
            mono = time.monotonic_ns()
            source = stamp.sec*1_000_000_000+stamp.nanosec
            key = (kind, parent, child)
            before = previous.get(key)
            write(dict(kind=kind, parent=parent, child=child, source_ns=source,
                       receive_ros_ns=now, receive_monotonic_ns=mono,
                       age_ms=(now-source)/1e6,
                       receive_gap_ms=None if before is None else (mono-before[0])/1e6,
                       source_gap_ms=None if before is None else (source-before[1])/1e6))
            previous[key] = (mono, source)
        def odom(message: Odometry) -> None:
            receive('odom', message.header.stamp, message.header.frame_id, message.child_frame_id)
        def tf(message: TFMessage) -> None:
            for transform in message.transforms:
                receive('tf', transform.header.stamp, transform.header.frame_id, transform.child_frame_id)
        subscriptions = [node.create_subscription(Odometry, '/harvest_01/odom', odom, qos_profile_sensor_data),
                         node.create_subscription(TFMessage, '/harvest_01/tf', tf, qos_profile_sensor_data)]
        next_snapshot = 0.
        try:
            while rclpy.ok() and not stop:
                rclpy.spin_once(node, timeout_sec=.05)
                if time.monotonic() >= next_snapshot:
                    write(dict(kind='processes', receive_ros_ns=node.get_clock().now().nanoseconds,
                               processes=process_snapshot()))
                    next_snapshot = time.monotonic()+5.
        finally:
            for subscription in subscriptions:
                node.destroy_subscription(subscription)
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
