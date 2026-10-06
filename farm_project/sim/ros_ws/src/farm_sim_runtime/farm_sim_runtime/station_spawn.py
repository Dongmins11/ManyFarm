"""시뮬 시작 station 설정과 USD session layer 배치. ROS/미션 코드는 사용하지 않습니다."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def read_station(config_path: Path, device: dict[str, Any]) -> dict[str, Any] | None:
    """장치 설정 옆의 생성된 station JSON을 읽습니다. 기존 설정은 선택적으로 지원합니다."""
    option = device.get('station_spawn', {})
    if not option.get('enabled', False):
        return None
    directory = config_path.resolve().parent
    path = (directory / option['config']).resolve()
    if not path.is_relative_to(directory):
        raise ValueError('station 설정은 장치 설정 폴더 안에 있어야 합니다.')
    data = json.loads(path.read_text())
    if data.get('schema_version') != 1 or data.get('map_id') != device['map_id']:
        raise ValueError('station 설정 schema/map_id 불일치')
    robot_id = device['robot_id']
    station = data['stations'][robot_id]
    xy, yaw = station['xy_m'], station['yaw_rad']
    if len(xy) != 2 or yaw is None or not all(math.isfinite(float(v)) for v in (*xy, yaw)):
        raise ValueError(f'{robot_id}: 유효한 station XY와 확정된 yaw가 필요합니다.')
    if station.get('status') == 'DESIGN_PROPOSAL':
        raise ValueError(f'{robot_id}: 설계안 station은 자동 배치에 사용할 수 없습니다.')
    return dict(station, robot_id=robot_id, T_map_world=data['T_map_world'], source=str(path))


def station_transforms(station: dict[str, Any], body_world: Any,
                       root_world: Any, parent_world: Any) -> tuple[Any, Any]:
    """map XY/yaw를 world 배치로 변환합니다. 기존 body 높이를 보존하며 root 전체를 이동합니다."""
    import numpy as np
    registration = np.asarray(station['T_map_world'], dtype=float)
    if (registration.shape != (4, 4) or not np.isfinite(registration).all()
            or not np.allclose(registration[3], [0, 0, 0, 1])
            or not np.allclose(registration[:3, :3].T @ registration[:3, :3], np.eye(3))
            or not np.isclose(np.linalg.det(registration[:3, :3]), 1)
            or not np.allclose(registration[:3, 2], [0, 0, 1])):
        raise ValueError('map/world 등록은 유한한 평면 강체 변환이어야 합니다.')
    old_map = registration @ body_world
    if (not np.allclose(old_map[:3, 2], [0, 0, 1], atol=1e-5)
            or not np.allclose(old_map[:3, :3].T @ old_map[:3, :3], np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(old_map[:3, :3]), 1)):
        raise ValueError('배치 전 로봇 body는 단위 scale의 수평 자세여야 합니다.')
    yaw = float(station['yaw_rad'])
    c, s = math.cos(yaw), math.sin(yaw)
    desired_map = np.eye(4)
    desired_map[:3, :3] = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    desired_map[:3, 3] = [*station['xy_m'], old_map[2, 3]]
    desired_body = np.linalg.inv(registration) @ desired_map
    desired_root = desired_body @ np.linalg.inv(body_world) @ root_world
    return np.linalg.inv(parent_world) @ desired_root, desired_body


def verify_station_pose(station: dict[str, Any], position: Any, orientation: Any) -> None:
    """물리 초기화가 배치를 되돌리지 않았는지 한 번 확인합니다. 위치추정에 주입하지 않습니다."""
    import numpy as np
    w, x, y, z = map(float, orientation)
    rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    world = np.eye(4)
    world[:3, :3], world[:3, 3] = rotation, position
    pose = np.asarray(station['T_map_world']) @ world
    yaw = math.atan2(pose[1, 0], pose[0, 0])
    if (math.dist(pose[:2, 3], station['xy_m']) > .005
            or abs(math.remainder(yaw - station['yaw_rad'], 2 * math.pi)) > .01):
        raise RuntimeError('물리 초기화 후 station 배치가 유지되지 않았습니다.')


def place_at_station(stage: Any, binding: dict[str, Any], station: dict[str, Any]) -> dict[str, Any]:
    """물리 초기화 전에 원본을 저장하지 않고 로봇 전체를 station으로 이동합니다."""
    import numpy as np
    from pxr import Gf, UsdGeom
    if stage.GetEditTarget().GetLayer() != stage.GetSessionLayer():
        raise RuntimeError('station 배치는 session layer에서만 허용합니다.')
    if binding.get('control_frame_yaw_rad', 0) != 0:
        raise ValueError('현재 단일 로봇 구동기는 별도 control frame을 지원하지 않습니다.')
    root = stage.GetPrimAtPath(binding['robot_prim'])
    body = stage.GetPrimAtPath(binding['robot_prim'].rstrip('/') + '/' + binding['articulation_relative'])
    if not root.IsValid() or not body.IsValid():
        raise RuntimeError('station 배치 대상 로봇 root/body가 없습니다.')
    cache = UsdGeom.XformCache()

    def matrix(prim: Any) -> Any:
        return np.asarray(cache.GetLocalToWorldTransform(prim), dtype=float).T

    parent = root.GetParent()
    parent_world = np.eye(4) if parent.IsPseudoRoot() else matrix(parent)
    local, desired = station_transforms(station, matrix(body), matrix(root), parent_world)
    xform = UsdGeom.Xformable(root)
    xform.ClearXformOpOrder()
    xform.SetResetXformStack(False)
    # 기존 동일 이름의 transform op가 있으면 새 순서에 다시 사용합니다.
    xform.AddTransformOp().Set(Gf.Matrix4d(*map(float, local.T.reshape(-1))))
    cache.Clear()
    actual = matrix(body)
    if not np.allclose(actual, desired, atol=1e-5):
        raise RuntimeError('station 배치 검증 실패: 하위 resetXformStack/변환을 확인하세요.')
    return dict(robot_id=station['robot_id'], node_id=station['node_id'],
                xy_map_m=station['xy_m'], yaw_map_rad=station['yaw_rad'],
                body_position_world_m=actual[:3, 3].tolist(), source=station['source'])
