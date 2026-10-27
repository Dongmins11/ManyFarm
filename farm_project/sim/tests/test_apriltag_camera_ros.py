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

    def test_transport_info_matches_common_docking_reliable_subscription(self) -> None:
        from rclpy.qos import QoSProfile, qos_check_compatible, QoSCompatibility, ReliabilityPolicy
        from unittest.mock import Mock
        cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        node = Mock()
        with patch('farm_sim_devices.camera_ros.RgbdReader'):
            CameraRos(node, cfg['camera'], cfg['frames']['camera_optical'])
        image_qos = node.create_publisher.call_args_list[0].args[2]
        info_qos = node.create_publisher.call_args_list[1].args[2]
        info_qos = QoSProfile(depth=info_qos) if isinstance(info_qos, int) else info_qos
        compatibility, _ = qos_check_compatible(info_qos, QoSProfile(depth=10))
        self.assertNotEqual(compatibility, QoSCompatibility.ERROR)
        self.assertEqual(info_qos.reliability, ReliabilityPolicy.RELIABLE)
        self.assertEqual(image_qos.reliability, ReliabilityPolicy.BEST_EFFORT)

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

    def test_scout_picam_uses_its_image_frame_and_calibration(self) -> None:
        cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout.json').read_text())
        camera = cfg['tag_camera']
        with patch('farm_sim_devices.camera_ros.RgbdReader') as reader:
            bridge = CameraRos(self,camera,cfg['frames']['tag_camera_optical'])
            reader.assert_called_once_with(camera['shm_name'])
            packet = dict(rgb=np.zeros((camera['height'],camera['width'],3),np.uint8),
                metadata=dict(session='scout',frame_id=cfg['frames']['camera_optical'],stamp_ns=2))
            reader.return_value.read.return_value = packet
            self.assertFalse(bridge.publish('scout'))  # 예찰 D435 프레임을 PiCam으로 발행하지 않습니다.
            packet['metadata']['frame_id'] = cfg['frames']['tag_camera_optical']
            self.assertTrue(bridge.publish('scout'))
            image,info = bridge.image_pub.messages[0],bridge.info_pub.messages[0]
            self.assertEqual(image.header.frame_id,'scout_01/picam_optical_frame')
            self.assertEqual(image.header,info.header)
            np.testing.assert_allclose(info.k,camera['camera_info']['k'])
            np.testing.assert_allclose(info.d,camera['camera_info']['d'])

    def test_future_image_waits_without_rewriting_capture_stamp(self) -> None:
        cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        with patch('farm_sim_devices.camera_ros.RgbdReader') as reader:
            bridge=CameraRos(self,cfg['camera'],cfg['frames']['camera_optical'])
            packet=dict(rgb=np.zeros((720,1280,3),np.uint8),metadata=dict(
                session='current',frame_id=cfg['frames']['camera_optical'],stamp_ns=100))
            reader.return_value.read.side_effect=[packet,None,None]
            self.assertFalse(bridge.publish('current',99))
            self.assertTrue(bridge.publish('current',100))
            self.assertEqual(bridge.image_pub.messages[0].header.stamp.nanosec,100)
            self.assertFalse(bridge.publish('current',101))

    def test_pending_image_dropped_on_session_change_or_clock_stall(self) -> None:
        cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        for new_session,elapsed in [('new',.1),('current',1.1)]:
            with patch('farm_sim_devices.camera_ros.RgbdReader') as reader, patch('farm_sim_devices.camera_ros.time.monotonic') as now:
                bridge=CameraRos(self,cfg['camera'],cfg['frames']['camera_optical'])
                packet=dict(rgb=np.zeros((720,1280,3),np.uint8),metadata=dict(
                    session='current',frame_id=cfg['frames']['camera_optical'],stamp_ns=100))
                reader.return_value.read.side_effect=[packet,None];now.return_value=10.
                self.assertFalse(bridge.publish('current',99))
                now.return_value=10.+elapsed
                self.assertFalse(bridge.publish(new_session,100))
                self.assertFalse(bridge.pending_packets)

    def test_capture_period_equal_to_delay_does_not_starve_publication(self) -> None:
        cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        with patch('farm_sim_devices.camera_ros.RgbdReader') as reader:
            bridge=CameraRos(self,cfg['camera'],cfg['frames']['camera_optical'])
            def packet(stamp):
                return dict(rgb=np.zeros((720,1280,3),np.uint8),metadata=dict(
                    session='current',frame_id=cfg['frames']['camera_optical'],stamp_ns=stamp))
            reader.return_value.read.side_effect=[packet(100),packet(200),packet(300),None]
            self.assertFalse(bridge.publish('current',0))
            self.assertTrue(bridge.publish('current',100))
            self.assertTrue(bridge.publish('current',200))
            self.assertTrue(bridge.publish('current',300))
            self.assertEqual([m.header.stamp.nanosec for m in bridge.image_pub.messages],[100,200,300])


if __name__ == '__main__':
    unittest.main()
