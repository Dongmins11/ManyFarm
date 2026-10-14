"""실제/가상 ROS 영상의 AprilTag 검출을 공통 관측기 Journal 계약으로 기록한다."""
from collections import OrderedDict
import json
from pathlib import Path

import numpy as np
from .detection import detection_payload


def prepare_capture(folder: Path, assets: dict, *, use_sim_time: bool = True) -> None:
    """launch 단계에서 빈 파일을 준비해 관측기와 검출기의 시작 순서 의존을 없앤다."""
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'settings.json').write_text(json.dumps(dict(
        calibration_sha256=assets['calibration_version'].split(':')[-1],
        source='ros_image', detector='apriltag_ros', use_sim_time=use_sim_time)) + '\n')
    (folder / 'detections.jsonl').touch()


def detection_record(message: object, optical_frame: str) -> dict:
    """검출기가 제공한 코너·margin·hamming만 전달하고 정답 좌표는 읽지 않는다."""
    if message.header.frame_id != optical_frame:
        raise ValueError('optical_frame_mismatch')
    detections = [detection_payload(detection) for detection in message.detections]
    stamp = message.header.stamp
    return dict(source_stamp_ns=int(stamp.sec)*1_000_000_000 + int(stamp.nanosec),
                frame_id=optical_frame, detections=detections)


def check_camera_info(message: object, expected: dict) -> None:
    """그림과 공통 기하 계산이 같은 K/D/광학 프레임을 사용해야 기록한다."""
    if (message.width, message.height, message.header.frame_id, message.distortion_model) != (
            expected['width'], expected['height'], expected['frame_id'], expected['distortion_model']):
        raise ValueError('camera_info_mismatch')
    for key in ('k', 'd', 'r', 'p'):
        actual, wanted = list(getattr(message, key)), expected[key]
        if len(actual) != len(wanted) or not np.allclose(actual, wanted, rtol=0, atol=1e-8):
            raise ValueError('camera_info_mismatch:' + key)


def main(args: list[str] | None = None) -> None:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from apriltag_msgs.msg import AprilTagDetectionArray
    from sensor_msgs.msg import CameraInfo

    class Capture(Node):
        def __init__(self) -> None:
            super().__init__('tag_capture')
            for key in ('assets_file', 'capture_directory'):
                self.declare_parameter(key, '')
            assets = json.loads(Path(self.get_parameter('assets_file').value).read_text())
            self.expected = assets['camera_info']
            self.info_stamps, self.pending = OrderedDict(), OrderedDict()
            self.last_stamp = -1
            self.journal = (Path(self.get_parameter('capture_directory').value) / 'detections.jsonl').open('a', buffering=1)
            self.information = self.create_subscription(CameraInfo, 'camera_info', self.on_info, qos_profile_sensor_data)
            self.detections = self.create_subscription(AprilTagDetectionArray, 'detections', self.on_detection, qos_profile_sensor_data)

        def on_info(self, message: object) -> None:
            try:
                check_camera_info(message, self.expected)
            except ValueError as error:
                self.get_logger().error(str(error))
                return
            stamp = int(message.header.stamp.sec)*1_000_000_000 + int(message.header.stamp.nanosec)
            self.info_stamps[stamp] = True
            while len(self.info_stamps) > 64:
                self.info_stamps.popitem(last=False)
            if stamp in self.pending:
                self.write(self.pending.pop(stamp))

        def on_detection(self, message: object) -> None:
            try:
                record = detection_record(message, self.expected['frame_id'])
            except ValueError as error:
                self.get_logger().error(str(error))
                return
            stamp = record['source_stamp_ns']
            if stamp in self.info_stamps:
                self.write(record)
            else:
                self.pending[stamp] = record
                while len(self.pending) > 64:
                    self.pending.popitem(last=False)

        def write(self, record: dict) -> None:
            stamp = record['source_stamp_ns']
            if stamp <= self.last_stamp or not 0 <= self.get_clock().now().nanoseconds-stamp <= 1_000_000_000:
                return
            self.journal.write(json.dumps(record, allow_nan=False) + '\n')
            self.last_stamp = stamp

    rclpy.init(args=args)
    node = None
    try:
        node = Capture()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.journal.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
