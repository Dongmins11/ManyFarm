"""가상 RGB 영상과 동일 촬영 시각의 보정 정보를 ROS 센서 토픽으로 발행합니다."""
import copy
import time
from collections import deque
from farm_common.rgbd_shm import RgbdReader
from sensor_msgs.msg import Image, CameraInfo
from rclpy.qos import qos_profile_sensor_data


class CameraRos:
    def __init__(self, node: object, config: dict, optical_frame: str) -> None:
        self.config = config
        self.frame = optical_frame
        self.reader = RgbdReader(config['shm_name'])
        self.pending_packets = deque(maxlen=4)
        self.image_pub = node.create_publisher(Image, config['ros_image_topic'], qos_profile_sensor_data)
        # 공통 도킹 서버는 CameraInfo를 reliable로 구독한다. 기존 영상 QoS는 유지한다.
        info_qos = 10 if config.get('ros_info_reliable', False) else qos_profile_sensor_data
        self.info_pub = node.create_publisher(CameraInfo, config['ros_info_topic'], info_qos)

    def publish(self, session: str | None, max_stamp_ns: int | None = None) -> bool:
        """현재 Isaac 세션의 새 프레임만 발행하며 이전 세션 영상은 버립니다."""
        if session is None:
            return False
        packet = self.reader.read(max_age=1., include_depth=False)
        if packet is not None:
            self.pending_packets.append((time.monotonic(),packet))
        # 대기시간과 촬영 주기가 같아도 새 프레임이 이전 프레임을 계속 밀어내지 않는다.
        # 발행 가능한 것 중 최신 한 장만 선택하고 미래 프레임은 유한 큐에 보관한다.
        packet = None
        while self.pending_packets:
            received,candidate=self.pending_packets[0]
            meta=candidate['metadata']
            if (meta['session']!=session or meta['frame_id']!=self.frame
                    or time.monotonic()-received>1.):
                self.pending_packets.popleft();continue
            if max_stamp_ns is not None and meta['stamp_ns']>max_stamp_ns:break
            _,packet=self.pending_packets.popleft()
        if packet is None:
            return False
        meta = packet['metadata']
        rgb = packet['rgb']
        if rgb.shape != (self.config['height'], self.config['width'], 3):
            raise ValueError('ROS 카메라 해상도와 렌더 해상도가 다릅니다.')
        image = Image()
        ns = meta['stamp_ns']
        image.header.stamp.sec = ns // 1000000000
        image.header.stamp.nanosec = ns % 1000000000
        image.header.frame_id = self.frame
        image.height, image.width = rgb.shape[:2]
        image.encoding = 'rgb8'; image.is_bigendian = 0; image.step = image.width * 3
        image.data = rgb.tobytes()
        info = CameraInfo()
        info.header = copy.deepcopy(image.header)
        info.width, info.height = image.width, image.height
        calibration = self.config['camera_info']
        info.distortion_model = calibration['distortion_model']
        for field in ('k', 'd', 'r', 'p'):
            setattr(info, field, [float(v) for v in calibration[field]])
        self.image_pub.publish(image)
        self.info_pub.publish(info)
        return True
