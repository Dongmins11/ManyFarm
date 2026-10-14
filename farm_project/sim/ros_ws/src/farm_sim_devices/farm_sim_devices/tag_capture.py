"""기존 시뮬 import/실행 경로 호환. ROS 검출 기록 구현은 공통 패키지가 소유한다."""
from farm_tag_localization.ros_capture import check_camera_info, detection_record, main, prepare_capture

__all__ = ["check_camera_info", "detection_record", "main", "prepare_capture"]
