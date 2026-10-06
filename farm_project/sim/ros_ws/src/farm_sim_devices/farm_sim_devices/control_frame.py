"""USD articulation 좌표와 ROS 주행 좌표 사이 강체 변환. 바퀴 부호도 논리 주행축 기준입니다."""
import math
import numpy as np


def asset_from_control(binding: dict) -> np.ndarray:
    yaw = float(binding.get('control_frame_yaw_rad', 0.0))
    if not math.isfinite(yaw):
        raise ValueError('control_frame_yaw_rad must be finite')
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c,-s,0.,0.], [s,c,0.,0.],
                     [0.,0.,1.,0.], [0.,0.,0.,1.]])


def station_root_transform(world_control: np.ndarray, world_asset: np.ndarray, world_root: np.ndarray, asset_control: np.ndarray) -> np.ndarray:
    """논리 주행 프레임이 station과 일치하도록 로봇 root를 배치합니다."""
    return world_control @ np.linalg.inv(world_asset @ asset_control) @ world_root


def relative_sensor_transforms(world_asset: np.ndarray, world_link: np.ndarray, world_scan: np.ndarray, asset_control: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """주행 프레임 기준 논리 base_link와 실제 scan 변환을 반환합니다."""
    control_world = np.linalg.inv(world_asset @ asset_control)
    return (control_world @ world_link @ asset_control,
            control_world @ world_scan)
