"""환경별 카메라 입력을 동일한 검출·관측·AMCL 보정 경로에 연결한다."""
from pathlib import Path
import json
import uuid


def ros_capture_actions(root: Path, profile: dict, *, use_sim_time: bool,
                        output_root: str, camera_namespace: str | None = None) -> tuple[list, str]:
    """실제/가상 카메라의 ROS image_raw·camera_info에 같은 검출기를 연결한다."""
    from ament_index_python.packages import get_package_share_directory
    from launch_ros.actions import Node
    from .runtime import resolve
    from .ros_capture import prepare_capture
    from .detection import detector_parameters_from_assets
    import yaml

    for package in ('apriltag_ros', 'image_proc'):
        try:
            get_package_share_directory(package)
        except LookupError as error:
            raise RuntimeError('ros-jazzy-apriltag-ros와 ros-jazzy-image-proc가 필요합니다.') from error
    tag_profile = yaml.safe_load(resolve(root, profile['tag_localization_config']).read_text())
    assets_file = resolve(root, tag_profile['assets_file'])
    assets = json.loads(assets_file.read_text())
    detector = detector_parameters_from_assets(assets, use_sim_time=use_sim_time,
                                               overrides=tag_profile.get('detector_parameters'))
    folder = resolve(root, output_root) / uuid.uuid4().hex
    prepare_capture(folder, assets, use_sim_time=use_sim_time)
    namespace = camera_namespace or profile['robot_id'] + '/apriltag_camera'
    return [
        Node(package='image_proc', executable='rectify_node', name='tag_rectify',
             namespace=namespace, output='screen',
             parameters=[dict(use_sim_time=use_sim_time, image_transport='raw', queue_size=5)],
             remappings=[('image', 'image_raw')]),
        Node(package='apriltag_ros', executable='apriltag_node', name='tag_detector',
             namespace=namespace, output='screen', parameters=[detector],
             remappings=[('/tf', 'diagnostic_tf'), ('/tf_static', 'diagnostic_tf_static')]),
        Node(package='farm_tag_localization', executable='tag_capture', namespace=namespace,
             output='screen', parameters=[dict(use_sim_time=use_sim_time, assets_file=str(assets_file),
                                              capture_directory=str(folder))])], str(folder)


def tag_launch_actions(root: Path, profile: dict, mode: str, *, enabled: bool,
                       camera_mode: str, capture_directory: str) -> tuple[bool, list]:
    """로봇 종류와 무관하게 입력 소유권·지도 바인딩을 검사하고 보정 노드를 만든다."""
    from launch_ros.actions import Node
    from farm_navigation.configuration import read_mapping, resolve_file
    from .runtime import validate_binding

    camera_on = camera_mode == 'true' or (camera_mode == 'auto' and mode == 'real'
                                         and enabled and not capture_directory)
    if camera_on and capture_directory:
        raise ValueError('자동 촬영과 외부 capture_directory를 동시에 지정할 수 없습니다.')
    if camera_on and mode != 'real':
        raise ValueError('실물 카메라 실행은 mode=real 전용입니다. sim은 외부 capture_directory를 사용하세요.')
    tag_path = None
    tag_sync = False
    if enabled:
        if not profile.get('tag_localization_config'):
            raise ValueError('tag_localization_config에 이 로봇의 카메라·태그 등록 파일이 필요합니다.')
        tag_path = resolve_file(root, profile['tag_localization_config'])
        if tag_path.is_relative_to(root / 'sim') != (mode == 'sim'):
            raise ValueError('태그 설정의 sim/real 경로 불일치')
        tag_config = read_mapping(tag_path)
        validate_binding(tag_config, profile, root)
        tag_sync = tag_config.get('correction_transport', 'initialpose') == 'scan_sync'
        if not camera_on and not capture_directory:
            raise ValueError('tag_correction=true에는 현재 capture_directory가 필요합니다.')
    actions = []
    if camera_on:
        if not profile.get('tag_capture_config'):
            raise ValueError('tag_capture_config에 실제 카메라 입력 연결이 필요합니다.')
        capture_config = resolve_file(root, profile['tag_capture_config'])
        config = read_mapping(capture_config)
        if config.get('configured') is False:
            raise ValueError('태그 카메라 연결 미완료: ' + str(config.get('setup_required', capture_config)))
        backend = config.get('backend', 'usb_session')
        if backend == 'ros':
            actions, capture_directory = ros_capture_actions(root, profile, use_sim_time=False,
                output_root=config['output_root'], camera_namespace=config.get('camera_namespace'))
        elif backend == 'usb_session':
            actions.append(Node(package='farm_tag_localization', executable='tag_capture_session',
                output='screen', sigterm_timeout='60', sigkill_timeout='5', arguments=[
                    '--project-root', str(root), '--capture-config', str(capture_config),
                    '--robot-id', profile['robot_id'],
                    *(['--correction-config', str(tag_path)] if enabled else [])]))
            return tag_sync, actions
        else:
            raise ValueError('알 수 없는 태그 카메라 backend: ' + str(backend))
    if enabled:
        tf_remaps = [] if mode == 'sim' else [
            ('/tf', '/' + profile['robot_id'] + '/tf'),
            ('/tf_static', '/' + profile['robot_id'] + '/tf_static')]
        actions.append(Node(package='farm_tag_localization', executable='tag_amcl_adapter',
            namespace=profile['robot_id'], output='screen', remappings=tf_remaps, parameters=[dict(
                project_root=str(root), config_file=str(tag_path),
                capture_directory=capture_directory, use_sim_time=mode == 'sim')]))
    return tag_sync, actions
