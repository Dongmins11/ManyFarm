"""시뮬 배치·카메라 원본에서 공통 AprilTag 관측기의 자산과 지도 바인딩을 생성한다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'sim/ros_ws/src/farm_sim_config/config'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version(data: object) -> str:
    return 'sha256:' + digest(json.dumps(data, sort_keys=True).encode())


def build() -> dict[str, dict]:
    """동일한 ID를 구간별로 보존한다. 실물 좌표·실물 픽셀 편향은 사용하지 않는다."""
    placement = json.loads((CONFIG / 'apriltag_map.json').read_text())
    environment = yaml.safe_load((CONFIG / 'harvest_runtime.yaml').read_text())
    map_path = ROOT / environment['map_yaml']
    image_path = map_path.parent / yaml.safe_load(map_path.read_text())['image']
    tags = []
    for tag in placement['tags']:
        transform = np.eye(4)
        # AprilTag C p[]/IPPE의 검출 좌표는 종이 표면의 right/outward와 x/z가 반대다.
        # 실제 Isaac 렌더→apriltag_ros 코너로 확인했으며 검출 코너 순서는 바꾸지 않는다.
        transform[:3, 0] = -np.asarray(tag['right_map'])
        transform[:3, 2] = -np.asarray(tag['normal_map'])
        transform[:3, 1] = np.cross(transform[:3, 2], transform[:3, 0])
        transform[:3, 3] = tag['tag_center_map_m']
        tags.append(dict(family=tag['family'], tag_id=tag['id'], section_id=tag['section_id'],
                         edge_m=tag['black_edge_m'], t_map_tag=transform.tolist()))
    result = {}
    for robot, camera_key, frame_key, asset_name, model_name in (
        ('harvest', 'camera', 'camera_optical', 'assets.json', 'observation_model.json'),
        ('scout', 'tag_camera', 'tag_camera_optical', 'scout_assets.json', 'scout_observation_model.json'),
    ):
        device = json.loads((CONFIG / (robot + '.json')).read_text())
        camera = deepcopy(device[camera_key]['camera_info'])
        camera['frame_id'] = device['frames'][frame_key]
        assets = dict(schema='physical-assets-v1', status='simulation_geometry',
            registration_evidence=dict(method='sim apriltag_map.json scene placement',
                                       confirmed_physical_accuracy=False),
            map_version=version([digest(map_path.read_bytes()), digest(image_path.read_bytes())]),
            tag_map_version=version(tags), calibration_version=version(camera),
            extrinsics_version=version(device[camera_key]['T_base_optical']),
            camera_info=camera, t_base_camera=device[camera_key]['T_base_optical'], tags=tags)
        if 'calibration_source' in device[camera_key]:
            assets['registration_evidence']['camera_model'] = device[camera_key]['calibration_source']
        profile = dict(configured=True, robot_id=device['robot_id'], map_id=device['map_id'],
            assets_file='sim/ros_ws/src/farm_sim_config/config/tag_localization/' + asset_name,
            model_file=('robot/config/localization/common_observation_model.json' if robot == 'harvest' else
                        'sim/ros_ws/src/farm_sim_config/config/tag_localization/' + model_name),
            map_yaml_sha256=digest(map_path.read_bytes()), map_image_sha256=digest(image_path.read_bytes()),
            map_frame=placement['frame_id'], odom_frame=device['frames']['odom'],
            base_frame=device['frames']['base_footprint'], correction_transport='scan_sync',
            lock_directory='sim/runs/locks')
        result['tag_localization/' + asset_name] = assets
        result['tag_localization/' + robot + '.yaml'] = profile
    return result


def main() -> None:
    for name, data in build().items():
        path = CONFIG / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False) if path.suffix == '.yaml' else
                        json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print('시뮬 공용 태그 자산 240개 및 예찰·수확 지도/카메라 바인딩 생성')


if __name__ == '__main__':
    main()
