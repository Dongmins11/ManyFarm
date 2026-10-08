"""시각 수확 시험의 정차 후보를 현재 과실과 기존 직선 정차선에서 계산한다.

정답 좌표는 시험 배치에만 사용한다. 조건 통과는 Teacher의 연속 근거리
입력 범위를 뜻하며 IK, 충돌 없는 팔 경로 또는 실제 수확 성공의 증명은 아니다.
이 모듈은 USD/PhysX 상태를 수정하지 않는다.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import math
from typing import Any

import numpy as np

from farm_sim_devices.teacher_device import continuous_near_mask


def _transform(value: Any, name: str) -> np.ndarray:
    """열벡터 방식의 유한한 강체 변환을 검사한다. 길이 단위는 m다."""
    result = np.asarray(value, dtype=float)
    if (result.shape != (4, 4) or not np.isfinite(result).all()
            or not np.allclose(result[3], [0., 0., 0., 1.], atol=1e-8)
            or not np.allclose(result[:3, :3].T @ result[:3, :3], np.eye(3), atol=1e-6)
            or not math.isclose(np.linalg.det(result[:3, :3]), 1., abs_tol=1e-6)):
        raise ValueError(name+'는 유한한 4x4 강체 변환이어야 합니다.')
    return result


def _intervals(origin: np.ndarray, slope: np.ndarray, bounds: tuple[float, float],
               config: Mapping[str, Any]) -> list[tuple[float, float]]:
    """arm root(y)가 작업 상자와 HOME 거리 띠 안에 드는 map Y 구간이다."""
    lower, upper = bounds
    for offset, direction, lo, hi in zip(origin, slope,
            config['workspace_arm_min_m'], config['workspace_arm_max_m']):
        if abs(direction) < 1e-12:
            if not lo <= offset <= hi:
                return []
            continue
        ends = sorted(((lo-offset)/direction, (hi-offset)/direction))
        lower, upper = max(lower, ends[0]), min(upper, ends[1])
    if upper-lower <= 1e-9:
        return []
    delta = origin-np.asarray(config['home_tcp_arm_m'], dtype=float)
    norm = float(slope @ slope)
    center = -float(slope @ delta)/norm
    closest = delta+center*slope
    distance_squared = float(closest @ closest)
    far = float(config['near_home_max_m'])
    if distance_squared >= far*far:
        return []
    radius = math.sqrt((far*far-distance_squared)/norm)
    lower, upper = max(lower, center-radius), min(upper, center+radius)
    if upper-lower <= 1e-9:
        return []
    near = float(config['near_home_min_m'])
    if distance_squared > near*near:
        return [(lower, upper)]
    radius = math.sqrt((near*near-distance_squared)/norm)
    # 최소 HOME 거리 내부는 제외하고 남은 양쪽 구간의 중앙을 사용한다.
    choices = [(lower, min(upper, center-radius)), (max(lower, center+radius), upper)]
    return [(lo, hi) for lo, hi in choices if hi-lo > 1e-9]


def find_placements(records: Sequence[Mapping[str, Any]], positions: np.ndarray,
                    attached: np.ndarray, excluded_ids: set[str],
                    sections: Mapping[str, Mapping[str, Any]], T_map_world: np.ndarray,
                    T_base_arm: np.ndarray, base_z_map: float,
                    device_config: Mapping[str, Any], *,
                    pose_is_clear: Callable[[dict], bool] | None = None) -> list[dict]:
    """기존 정차선 안에서 부착된 빨강/노랑을 시도할 수 있는 배치를 반환한다.

    positions는 records와 같은 순서의 현재 world root 좌표(N,3), attached는
    현재 줄기 부착 여부(N)다. 제외 ID에는 이미 시도한 persistent prim path를
    전달한다. T_base_arm은 실제 논리 주행 프레임에서 오른팔 장착점으로의
    변환이다. x/y/yaw는 map 기준, T_world_base는 world 기준이다.

    현재 설정의 harvest_route는 x_m/heading_rad, Y 범위는 같은 Section의
    survey_geometry.start_xy_m/end_xy_m에서 읽는다. 양 끝 밖으로 배치하지
    않으며 정차선의 X나 heading을 임의 보정하지 않는다. pose_is_clear가
    있으면 후보 dict를 전달해 지도/차체 footprint 검사를 통과한 것만 남긴다.
    """
    points = np.asarray(positions, dtype=float)
    attached_mask = np.asarray(attached, dtype=bool)
    if (points.shape != (len(records), 3) or not np.isfinite(points).all()
            or attached_mask.shape != (len(records),)):
        raise ValueError('현재 과실 좌표(N,3)와 부착 여부(N)의 순서/크기를 확인하세요.')
    map_world = _transform(T_map_world, 'T_map_world')
    base_arm = _transform(T_base_arm, 'T_base_arm')
    if not math.isfinite(base_z_map):
        raise ValueError('base_z_map은 유한한 map 높이(m)여야 합니다.')
    continuous_near_mask(np.empty((0, 3)), device_config)
    paths = [record['prim_path'] for record in records]
    if (any(not isinstance(path, str) or not path.startswith('/') for path in paths)
            or len(set(paths)) != len(paths)):
        raise ValueError('과실에는 중복 없는 절대 prim_path가 필요합니다.')
    eligible = attached_mask & np.asarray([
        record.get('color') in ('red', 'yellow') and path not in excluded_ids
        for path, record in zip(paths, records)], dtype=bool)
    points_map = points @ map_world[:3, :3].T+map_world[:3, 3]
    world_map = np.linalg.inv(map_world)
    result, seen = [], set()
    for section_id, section in sorted(sections.items()):
        route, geometry = section['harvest_route'], section['survey_geometry']
        x, yaw = float(route['x_m']), float(route['heading_rad'])
        start, end = (np.asarray(geometry[key], dtype=float) for key in ('start_xy_m', 'end_xy_m'))
        if (start.shape != (2,) or end.shape != (2,) or not np.isfinite([*start, *end, x, yaw]).all()
                or not math.isclose(start[0], end[0], abs_tol=1e-7)
                or not math.isclose(math.cos(yaw), 0., abs_tol=1e-7)):
            raise ValueError(str(section_id)+': 현재 x_m 형식은 Y 방향 직선 정차선만 지원합니다.')
        bounds = (float(min(start[1], end[1])), float(max(start[1], end[1])))
        if bounds[1]-bounds[0] <= 1e-9:
            raise ValueError(str(section_id)+': 정차선의 길이가 0입니다.')
        bed = section['evaluation_bed_prim'].rstrip('/')+'/'
        section_mask = eligible & np.asarray([path.startswith(bed) for path in paths], dtype=bool)
        if not section_mask.any():
            continue
        c, s = math.cos(yaw), math.sin(yaw)
        map_base = np.array([[c, -s, 0., x], [s, c, 0., 0.],
                             [0., 0., 1., base_z_map], [0., 0., 0., 1.]])
        arm_map = np.linalg.inv(map_base @ base_arm)
        origins = points_map @ arm_map[:3, :3].T+arm_map[:3, 3]
        slope = -arm_map[:3, 1]
        for index in np.flatnonzero(section_mask):
            for lower, upper in _intervals(origins[index], slope, bounds, device_config):
                y = (lower+upper)/2.
                key = (str(section_id), round(x, 8), round(y, 8), round(yaw, 8))
                if key in seen:
                    continue
                arm_points = origins+y*slope
                mask = section_mask & continuous_near_mask(arm_points, device_config)
                if not mask[index]:
                    continue
                seen.add(key)
                map_base[1, 3] = y
                indices = np.flatnonzero(mask)
                candidate = dict(section_id=section_id, x=x, y=y, yaw=yaw,
                    source_target_id=paths[index], target_ids=[paths[i] for i in indices],
                    target_world_m=points[index].tolist(), T_world_base=(world_map @ map_base).tolist())
                if pose_is_clear is None or pose_is_clear(candidate):
                    result.append(candidate)
    return result


def footprint_is_clear(free_cells: np.ndarray, resolution: float, origin: Sequence[float],
                       footprint: np.ndarray, pose_xy_yaw: Sequence[float],
                       padding_m: float = 0.) -> bool:
    """map 좌표 차체 다각형 전체가 알려진 자유 셀에 있는지 보수적으로 검사한다.

    free_cells는 row 0이 지도 최소 Y인 (H,W) bool 배열이다. occupancy 이미지의
    위/아래 반전과 occupied/unknown 분류는 호출자가 지도 YAML 기준으로 한다.
    origin과 pose는 (x[m], y[m], yaw[rad]), footprint는 논리 base 기준(N,2)다.
    셀 중심부터 다각형까지 padding+셀 반대각선 이내도 검사해 경계 누락을 막는다.
    """
    grid, polygon = np.asarray(free_cells), np.asarray(footprint, dtype=float)
    map_origin, pose = np.asarray(origin, dtype=float), np.asarray(pose_xy_yaw, dtype=float)
    if (grid.ndim != 2 or not grid.size or grid.dtype != np.dtype(bool)
            or polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3
            or map_origin.shape != (3,) or pose.shape != (3,)
            or not np.isfinite(polygon).all() or not np.isfinite(map_origin).all()
            or not np.isfinite(pose).all() or not math.isfinite(resolution) or resolution <= 0
            or not math.isfinite(padding_m) or padding_m < 0):
        raise ValueError('자유 셀 배열, 지도 해상도/원점, 차체 다각형과 배치 pose를 확인하세요.')
    c, s = math.cos(pose[2]), math.sin(pose[2])
    world_points = polygon @ np.array([[c, s], [-s, c]])+pose[:2]
    c, s = math.cos(map_origin[2]), math.sin(map_origin[2])
    local = (world_points-map_origin[:2]) @ np.array([[c, -s], [s, c]])
    edge_vectors = np.roll(local, -1, axis=0)-local
    edge_lengths = np.sum(edge_vectors*edge_vectors, axis=1)
    area = abs(float(np.sum(local[:, 0]*np.roll(local[:, 1], -1)
                            -local[:, 1]*np.roll(local[:, 0], -1))))/2.
    if area < 1e-12 or np.any(edge_lengths < 1e-12):
        raise ValueError('차체 footprint는 넓이가 있고 중복 꼭짓점이 없는 다각형이어야 합니다.')
    margin = padding_m+resolution/math.sqrt(2.)
    first = np.floor((local.min(0)-margin)/resolution).astype(int)
    last = np.floor((local.max(0)+margin)/resolution).astype(int)
    if (np.any(first < 0) or last[0] >= grid.shape[1] or last[1] >= grid.shape[0]):
        return False
    columns, rows = np.meshgrid(np.arange(first[0], last[0]+1), np.arange(first[1], last[1]+1))
    centers = np.stack(((columns+.5)*resolution, (rows+.5)*resolution), axis=-1)
    inside = np.zeros(columns.shape, dtype=bool)
    near_edge = np.zeros(columns.shape, dtype=bool)
    for a, vector, length in zip(local, edge_vectors, edge_lengths):
        b = a+vector
        crossing = (a[1] > centers[..., 1]) != (b[1] > centers[..., 1])
        if abs(vector[1]) > 1e-12:
            inside ^= crossing & (centers[..., 0] < a[0]+vector[0]*(centers[..., 1]-a[1])/vector[1])
        fraction = np.clip(np.sum((centers-a)*vector, axis=-1)/length, 0., 1.)
        nearest = a+fraction[..., None]*vector
        near_edge |= np.sum((centers-nearest)**2, axis=-1) <= margin*margin+1e-12
    checked = inside | near_edge
    return bool(checked.any() and grid[rows[checked], columns[checked]].all())
