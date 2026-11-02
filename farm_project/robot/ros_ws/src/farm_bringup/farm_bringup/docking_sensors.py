"""실물 도킹 입력 설정. 장착 변환은 여기서 생성하지 않는다."""
from pathlib import Path
import math
import re
import yaml


def load_docking_sensors(root, filename):
    root = Path(root).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError('도킹 센서 파일은 project_root 안에 있어야 합니다.')
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('도킹 센서 schema_version=1 필요')
    topics = data.get('topics', {})
    for name in ('image', 'camera_info', 'scan', 'odom'):
        value = topics.get(name)
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*', value):
            raise ValueError(f'{name}: 로봇 namespace 기준 상대 토픽 필요')
    if data.get('scan_is_filtered') is not True:
        raise ValueError('필터된 도킹 scan 입력을 명시해야 합니다.')
    frame = data.get('base_frame')
    if not isinstance(frame, str) or not frame or frame.startswith('/'):
        raise ValueError('base_frame 필요')
    timing = data.get('freshness', {})
    parameters = {}
    for key in ('odom_max_age_s', 'scan_max_age_s', 'image_header_max_age_s', 'image_receive_timeout_s', 'sensor_ready_timeout_s'):
        value = timing.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key}: 양의 유한 시간 필요')
        parameters[key] = float(value)
    parameters.update(image_topic=topics['image'], info_topic=topics['camera_info'], lidar_topic=topics['scan'])
    parameters.update(camera_parameters(data))
    pose_mode = data.get('marker_pose_mode', 'legacy_camera')
    if pose_mode not in ('legacy_camera', 'tf_observe'):
        raise ValueError('Unknown marker_pose_mode')
    parameters.update(marker_pose_mode=pose_mode, marker_base_frame=frame)
    control = data.get('pose_control', {})
    if control:
        target_file = (root / control['file']).resolve()
        if not target_file.is_relative_to(root) or not target_file.is_file():
            raise ValueError('pose_control file must exist inside project_root')
        if type(control.get('output_enabled',False)) is not bool:raise ValueError('pose_control.output_enabled must be bool')
        parameters.update(pose_control_file=str(target_file), pose_control_target=control['target'],pose_output_enabled=control.get('output_enabled',False))
    return data, parameters


def camera_parameters(data):
    camera = data.get('camera', {'backend': 'ros'})
    if not isinstance(camera, dict) or camera.get('backend') not in ('ros', 'picamera2'):
        raise ValueError('camera.backend: ros 또는 picamera2 필요')
    params = {'camera_input_backend': camera['backend']}
    if camera['backend'] == 'ros':
        return params
    if camera.get('geometry_verified') is not True:
        raise ValueError('직접 캡처 sensor mode/crop과 보정 조건 확인 필요')
    for key in ('width', 'height', 'sensor_width', 'sensor_height', 'sensor_bit_depth'):
        if type(camera.get(key)) is not int or camera[key] <= 0:
            raise ValueError(f'camera.{key}: 양의 정수 필요')
    if type(camera.get('index')) is not int or camera['index'] < 0:
        raise ValueError('camera.index: 0 이상의 정수 필요')
    fps = camera.get('fps')
    if type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0:
        raise ValueError('camera.fps: 양의 유한 값 필요')
    crop = camera.get('crop')
    if (not isinstance(crop, list) or len(crop) != 4
            or any(type(x) is not int for x in crop)
            or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
        raise ValueError('camera.crop: [x,y,width,height] 필요')
    for key in ('calibration_file', 'frame_id'):
        if not isinstance(camera.get(key), str) or not camera[key].strip():
            raise ValueError(f'camera.{key} 필요')
    for key in ('width', 'height', 'sensor_width', 'sensor_height', 'sensor_bit_depth',
                'index', 'crop', 'calibration_file', 'frame_id', 'geometry_verified'):
        params['camera_' + key] = camera[key]
    params['camera_fps'] = float(fps)
    return params


def camera_runtime_options(data):
    """Only the precision process uses this interpreter; other ROS nodes stay intact."""
    if data.get('camera', {}).get('backend', 'ros') != 'picamera2':
        return {}
    import os
    import shlex
    runtime = data.get('camera_runtime', {})
    python = Path(runtime.get('python_executable', '')).expanduser()
    paths = [Path(p).expanduser() for p in runtime.get('python_paths', [])]
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError('camera_runtime.python_executable must be an installed executable')
    if not paths or any(not p.is_absolute() or not p.is_dir() for p in paths):
        raise ValueError('camera_runtime.python_paths must be installed directories')
    pythonpath = os.pathsep.join([*(str(p) for p in paths), os.environ.get('PYTHONPATH', '')])
    return dict(prefix=shlex.quote(str(python)), additional_env={'PYTHONPATH': pythonpath})
