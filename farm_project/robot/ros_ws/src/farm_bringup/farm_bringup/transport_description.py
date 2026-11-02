"""확정 장착 형상에 실물 장치 설정의 카메라 외부 파라미터를 적용한다."""
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def _vector(config: dict, key: str) -> str:
    """유한한 xyz/rpy 세 성분을 URDF 속성으로 변환한다(m/rad)."""
    values = config[key]
    if not isinstance(values, list) or len(values) != 3:
        raise ValueError(f'{key}는 세 성분이어야 합니다.')
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) for v in values):
        raise ValueError(f'{key}는 유한한 수여야 합니다.')
    return ' '.join(str(v) for v in values)


def load_description(config: dict, directory: Path, *, full: bool = False) -> str:
    """카메라 위치 원본 devices.json으로 장착/전체 URDF를 구성한다."""
    if config['model'] != 'burger':
        raise ValueError('확정 장착 모델은 Burger 전용입니다.')
    filename = 'scout_burger.urdf' if full else config['mount_description']['file']
    if filename not in ('scout_mount.urdf', 'scout_burger.urdf') or (not full and filename != 'scout_mount.urdf'):
        raise ValueError('실물 보조 publisher에는 scout_mount.urdf만 사용합니다.')
    root = ET.parse(directory / filename).getroot()
    links = {e.get('name') for e in root.findall('link')}
    joints = {e.find('child').get('link'): e for e in root.findall('joint')}
    for key in ('camera_mount', 'pi_camera_mount'):
        mount = config[key]
        parent, child, optical = (mount[k] for k in ('parent_frame', 'link_frame', 'optical_frame'))
        # 이 확정 모델의 프레임 계약을 유지하고 잘못된 이름 변경은 거절한다.
        expected = ('bmany_camera_link', 'camera_color_optical_frame') if key == 'camera_mount' else ('picam_frame', 'picam_optical_frame')
        if parent != 'base_footprint' or (child, optical) != expected:
            raise ValueError(f'{key}의 프레임 계약이 확정 모델과 다릅니다.')
        if not {parent, child, optical} <= links:
            raise ValueError(f'{key} 프레임이 URDF에 없습니다.')
        joint = joints[child]
        joint.find('parent').set('link', parent)
        joint.find('origin').set('xyz', _vector(mount, 'xyz_m'))
        joint.find('origin').set('rpy', _vector(mount, 'rpy_rad'))
        optical_joint = joints[optical]
        optical_joint.find('parent').set('link', child)
        optical_joint.find('origin').set('rpy', _vector(mount, 'optical_rpy_rad'))
    if not full:
        forbidden = {'base_link', 'base_scan', 'imu_link', 'wheel_left_link', 'wheel_right_link'}
        if links & forbidden or any(j.get('type') != 'fixed' for j in joints.values()):
            raise ValueError('보조 URDF에 기존 Burger TF 또는 구동 관절이 포함되었습니다.')
    return ET.tostring(root, encoding='unicode')
