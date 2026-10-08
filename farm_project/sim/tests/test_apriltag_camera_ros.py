"""ROS 메시지 생성 검사. DDS/실물 USB/실제 주행 검증은 포함하지 않습니다."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sim/ros_ws/src/farm_sim_devices'), str(ROOT/'robot/ros_ws/src/farm_common')]
try:
    from farm_sim_devices.camera_ros import CameraRos
except ImportError:
    CameraRos = None


class Publisher:
    def __init__(self) -> None:
        self.messages = []

    def publish(self, message: object) -> None:
        self.messages.append(message)


@unittest.skipIf(CameraRos is None, 'ROS Jazzy 환경을 source한 뒤 실행하세요.')
class CameraTests(unittest.TestCase):
    def create_publisher(self, message_type: object, topic: str, qos: object) -> Publisher:
        return Publisher()

    def test_image_info_sync_and_old_session_rejection(self) -> None:
        cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/harvest.json').read_text())
        with patch('farm_sim_devices.camera_ros.RgbdReader') as reader:
            bridge = CameraRos(self,cfg['camera'],cfg['frames']['camera_optical'])
            packet = dict(rgb=np.zeros((720,1280,3),np.uint8),metadata=dict(
                session='current',frame_id=cfg['frames']['camera_optical'],stamp_ns=1234567890))
            reader.return_value.read.return_value = packet
            self.assertTrue(bridge.publish('current'))
            image = bridge.image_pub.messages[0]; info = bridge.info_pub.messages[0]
            self.assertEqual(image.header,info.header)
            self.assertEqual(image.header.stamp.sec,1)
            self.assertEqual(image.header.stamp.nanosec,234567890)
            self.assertEqual(image.encoding,'rgb8')
            self.assertEqual(len(image.data),1280*720*3)
            np.testing.assert_allclose(info.k,cfg['camera']['camera_info']['k'])
            np.testing.assert_allclose(info.d,cfg['camera']['camera_info']['d'])
            self.assertFalse(bridge.publish('other-session'))
            self.assertEqual(len(bridge.image_pub.messages),1)
            reader.return_value.read.return_value = None
            self.assertFalse(bridge.publish('current'))


if __name__ == '__main__':
    unittest.main()
