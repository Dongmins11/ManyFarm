"""화면 위치에 따른 관측 편향의 선택적 시험 보상. 주행 명령/취소 기능 없음."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from .runtime import resolve


def load_profile(config: dict, root: Path) -> dict | None:
    """명시한 프로파일만 사용한다. 자산/로봇/지도 불일치는 시작 전에 알린다."""
    name = config.get('pixel_bias_profile')
    if not name:
        return None
    p = json.loads(resolve(root, name).read_text())
    if p['schema_version'] != 1 or p['experimental'] is not True:
        raise ValueError('pixel_bias_profile_schema')
    for key in ('robot_id', 'map_id', 'map_frame'):
        if p[key] != config[key]:
            raise ValueError('pixel_bias_identity:' + key)
    for key in ('assets_file', 'model_file'):
        if hashlib.sha256(resolve(root, config[key]).read_bytes()).hexdigest() != p['sha256'][key]:
            raise ValueError('pixel_bias_asset_changed:' + key)
    for key in ('map_yaml_sha256', 'map_image_sha256'):
        if p[key] != config[key]:
            raise ValueError('pixel_bias_map_changed:' + key)
    normal = np.asarray(p['wall_normal_map'], float)
    if normal.shape != (2,) or not np.isfinite(normal).all() or not np.isclose(np.linalg.norm(normal), 1.):
        raise ValueError('pixel_bias_wall_normal')
    for key in ('distance_bias_m', 'yaw_bias_rad', 'u_interval_px', 'heading_interval_rad'):
        values = np.asarray(p[key], float)
        if values.shape != (2,) or not np.isfinite(values).all():
            raise ValueError('pixel_bias_invalid:' + key)
    if not (0 <= p['u_interval_px'][0] < p['u_interval_px'][1] <= 1280):
        raise ValueError('pixel_bias_u_interval')
    for key in ('u_scale_px', 'max_distance_bias_m', 'max_yaw_bias_rad'):
        if not math.isfinite(p[key]) or p[key] <= 0:
            raise ValueError('pixel_bias_limit:' + key)
    if not math.isfinite(p['u_center_px']) or not p['tag_ids']:
        raise ValueError('pixel_bias_domain')
    return p


def compensate(candidate: dict, profile: dict | None) -> tuple[np.ndarray, dict]:
    """촬영 시각 map pose의 벽 법선·yaw만 보상한다. 그 뒤 기존 odom 시각 보상을 한다."""
    raw = np.asarray(candidate['q'], float)
    if raw.shape != (3,) or not np.isfinite(raw).all():
        raise ValueError('pixel_bias_nonfinite_pose')
    if profile is None:
        return raw.copy(), dict(enabled=False)
    tag = candidate['_bias_tag']
    if tag[0] != profile['family'] or tag[1] not in profile['tag_ids']:
        raise ValueError('pixel_bias_unvalidated_tag')
    corners = np.asarray(candidate['_bias_corners'], float)
    if corners.shape != (4, 2) or not np.isfinite(corners).all():
        raise ValueError('pixel_bias_invalid_corners')
    u = float(corners[:, 0].mean())
    if not profile['u_interval_px'][0] <= u <= profile['u_interval_px'][1]:
        raise ValueError('pixel_bias_outside_measured_image_range')
    if not profile['heading_interval_rad'][0] <= raw[2] <= profile['heading_interval_rad'][1]:
        raise ValueError('pixel_bias_outside_measured_heading')
    normalized = (u - profile['u_center_px']) / profile['u_scale_px']
    distance = float(np.dot(profile['distance_bias_m'], [1., normalized]))
    yaw = float(np.dot(profile['yaw_bias_rad'], [1., normalized]))
    if abs(distance) > profile['max_distance_bias_m'] or abs(yaw) > profile['max_yaw_bias_rad']:
        raise ValueError('pixel_bias_excessive_adjustment')
    corrected = raw.copy()
    # 거리 과대 추정분을 벽 방향의 추정 위치에 반영한다. 실제 이동 명령이 아니다.
    corrected[:2] += np.asarray(profile['wall_normal_map']) * distance
    corrected[2] = math.atan2(math.sin(raw[2] - yaw), math.cos(raw[2] - yaw))
    return corrected, dict(enabled=True, model_id=profile['model_id'], tag=tag, u_px=u,
        source_raw=raw.tolist(), source_adjusted=corrected.tolist(),
        distance_bias_m=distance, yaw_bias_rad=yaw)
