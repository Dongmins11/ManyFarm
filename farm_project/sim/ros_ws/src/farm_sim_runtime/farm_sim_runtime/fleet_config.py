"""ROS/Isaac import 없이 다중 로봇 실행 설정 충돌을 검사합니다."""
import json
import math
import numpy as np
from pathlib import Path


def load_fleet(root: Path, path: Path) -> tuple[list, dict]:
    def read(value: str | Path) -> dict:
        file = (root / value).resolve()
        if not file.is_relative_to(root / 'sim'):
            raise ValueError('다중 시뮬 설정은 sim 안에 있어야 합니다.')
        return json.loads(file.read_text())
    fleet = read(path)
    stations = read(fleet['station_config'])
    registration = np.asarray(stations['T_map_world'], dtype=float)
    if (registration.shape != (4,4) or not np.isfinite(registration).all()
            or not np.allclose(registration[3], [0,0,0,1])
            or not np.allclose(registration[:3,:3].T @ registration[:3,:3], np.eye(3))
            or not np.isclose(np.linalg.det(registration[:3,:3]), 1)
            or not np.allclose(registration[:3,2], [0,0,1])):
        raise ValueError('map/world 등록은 평면 강체 변환이어야 합니다.')
    configs = [read(value) for value in fleet['device_configs']]
    ids, ports, frames, cameras = set(), set(), set(), set()
    for config in configs:
        if config['robot_id'] in ids or config['map_id'] != stations['map_id']:
            raise ValueError('중복 robot_id 또는 map_id 불일치')
        ids.add(config['robot_id'])
        station = stations['stations'][config['robot_id']]
        if station.get('yaw_rad') is None or station.get('status') == 'DESIGN_PROPOSAL':
            raise ValueError('확정된 station XY/yaw가 필요합니다.')
        if len(station['xy_m']) != 2 or not all(math.isfinite(float(v)) for v in (*station['xy_m'], station['yaw_rad'])):
            raise ValueError('station XY/yaw 값 오류')
        for key in ('command_port', 'telemetry_port'):
            port = config['runtime'][key]
            if not isinstance(port, int) or not 1024 <= port <= 65535:
                raise ValueError('장치 포트 범위 오류')
            if port in ports: raise ValueError('가상 장치 포트 충돌')
            ports.add(port)
        for frame in config['frames'].values():
            if frame in frames: raise ValueError('로봇 TF 이름 충돌')
            frames.add(frame)
        if config['camera']['enabled']:
            name = config['camera']['shm_name']
            if name in cameras: raise ValueError('카메라 공유 메모리 이름 충돌')
            cameras.add(name)
    if any(c.get('publish_clock', True) for c in configs):
        raise ValueError('fleet의 clock은 독립 relay만 발행해야 합니다.')
    for port in fleet['clock'].values():
        if port in ports: raise ValueError('clock 포트 충돌')
        ports.add(port)
    if len({c['scene'] for c in configs}) != 1 or len({(c['runtime']['physics_hz'], c['runtime']['render_hz']) for c in configs}) != 1:
        raise ValueError('로봇들은 같은 씬과 물리/렌더 주기를 사용해야 합니다.')
    evaluation = read(fleet['evaluation_config'])
    if evaluation['robot_id'] not in ids or evaluation['map_id'] != stations['map_id']:
        raise ValueError('평가 대상 로봇/지도 불일치')
    output = (root / evaluation['evaluation']['snapshot_file']).resolve()
    if not output.is_relative_to(root / 'sim'):
        raise ValueError('정답 snapshot은 sim 안에 저장해야 합니다.')
    harvest = dict(evaluation['evaluation'], robot_id=evaluation['robot_id'], scene_snapshot_file=str(output))
    return configs, dict(map_id=stations['map_id'], stations=stations['stations'],
                         evaluation=dict(T_map_world=stations['T_map_world']), harvest_robot=harvest, clock=fleet['clock'])
