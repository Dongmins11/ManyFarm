"""공통 벽 분석 결과를 고정 좌표로 변환하는 읽기 전용 어댑터."""
from __future__ import annotations
import math
import numpy as np
from .wall_reference import scan_points, fit_wall


def rotated_sectors(sectors: list, angle_deg: float) -> list[tuple[float, float]]:
    """관측 영역을 회전하고 ±180도 경계에서 나눈다. 폭은 늘리지 않는다."""
    result = []
    for lo, hi in sectors:
        if not -180 <= lo < hi <= 180:
            raise ValueError('벽 관측 영역 오류')
        start = (lo+angle_deg+180) % 360-180
        end = start+hi-lo
        if end <= 180:
            result.append((start, end))
        else:
            result.extend(((start, 180.), (-180., end-360.)))
    return result


class WallTracker:
    """벽 직선의 연속성을 고정 프레임에서 비교한다. 다른 벽 자동 선택은 하지 않는다."""
    def __init__(self, config: dict) -> None:
        self.config = config
        self.last = None
        self.anchor = None
        self.count = 0

    def observe(self, record: dict) -> dict:
        c = self.config
        stamp = int(record['stamp_ns'])
        if stamp <= 0 or (self.last and stamp <= self.last['stamp_ns']):
            raise ValueError('벽 관측 시각 중복/역행')
        matrix = np.asarray(record['odom_from_base'], dtype=float)
        if matrix.shape != (4,4) or not np.isfinite(matrix).all():
            raise ValueError('고정 프레임 변환 오류')
        # 평면 운동만 지원. 기울어진 TF를 조용히 2D로 투영하지 않는다.
        if np.max(np.abs(matrix[2,:2])) > .01 or abs(matrix[2,2]-1) > .01:
            raise ValueError('평면 밖 차체 자세')
        # 관측 영역을 결합한다. 후방은 ±180도 경계 양쪽 영역을 사용한다.
        sectors = c.get('sectors_deg', [c.get('sector_deg')])
        if c.get('follow_wall_normal', False) and self.anchor is not None:
            # 저장한 같은 벽의 odom 법선으로 관측 영역만 회전한다. 기준 자세/TF는 수정하지 않는다.
            body_yaw = math.atan2(matrix[1, 0], matrix[0, 0])
            shift = math.remainder(self.anchor['yaw']-body_yaw-c.get('normal_center_rad', 0.), math.tau)
            sectors = rotated_sectors(sectors, math.degrees(shift))
        points = np.concatenate([scan_points(record, tuple(sector)) for sector in sectors])
        wall = fit_wall(points,
                        threshold_m=c['fit_threshold_m'], min_points=c['min_points'],
                        min_ratio=c['min_ratio'], min_span_m=c['min_span_m'])
        if wall['residual_rms_m'] > c['max_rms_m']:
            raise ValueError('벽 직선 잔차 초과')
        if not c.get('min_distance_m', 0.) <= wall['distance_m'] <= c.get('max_distance_m', math.inf):
            raise ValueError('벽 거리 범위 초과')
        relative_angle = math.remainder(wall['normal_angle_rad'] - c.get('normal_center_rad', 0.), math.tau)
        if abs(relative_angle) > c.get('max_angle_rad', math.pi):
            raise ValueError('전방 벽 각도 범위 초과')
        normal = matrix[:2,:2] @ np.asarray(wall['normal_xy'])
        normal /= np.linalg.norm(normal)
        point = matrix[:2,3] + wall['distance_m'] * normal
        angle = math.atan2(normal[1], normal[0])
        result = dict(stamp_ns=stamp, x=float(point[0]), y=float(point[1]), yaw=angle,
                      distance_m=wall['distance_m'], angle_rad=wall['normal_angle_rad'],
                      rms_m=wall['residual_rms_m'], ready=False)
        for prior in (self.last, self.anchor):
            if prior:
                da = math.atan2(math.sin(angle-prior['yaw']), math.cos(angle-prior['yaw']))
                delta = abs(float((point - np.array([prior['x'],prior['y']])) @ normal))
                if abs(da)>c['normal_jump_rad'] or delta>c['plane_jump_m']:
                    raise ValueError('벽 후보 변경 또는 위치 추정 불연속')
        if self.last and (stamp-self.last['stamp_ns'])*1e-9>c['max_gap_s']:
            if not c.get('reacquire_after_gap', False):
                raise ValueError('벽 관측 간격 초과')
            # 같은 벽 anchor 검사를 통과한 경우에만 연속 표본 수를 다시 센다.
            self.count = 0
        self.last=result
        if self.anchor is None:self.anchor=result
        self.count += 1
        result['ready']=self.count>=c['stable_frames']
        return result


def docking_target(walls: dict, references: dict, odom_from_base: np.ndarray) -> dict:
    """동일 시각 선택 벽의 현재/티칭 법선·거리로 목표 자세를 계산한다(m/rad).

    벽이 직각/평행이라고 강제하지 않는다. 좌우 벽은 하나의 횡오차에 함께 기여한다.
    입력 벽 각도는 base 기준이며 결과는 odom 기준 목표다. 속도를 발행하지 않는다.
    """
    names = tuple(walls)
    angles = np.array([walls[n]['angle_rad'] for n in names])
    reference_angles = np.array([references[n]['normal_angle_rad'] for n in names])
    delta = angles - reference_angles
    yaw = math.atan2(float(np.sin(delta).sum()), float(np.cos(delta).sum()))
    normals = np.column_stack((np.cos(angles), np.sin(angles)))
    distances = np.array([walls[n]['distance_m'] - references[n]['distance_m'] for n in names])
    if not np.isfinite(normals).all() or not np.isfinite(distances).all():
        raise ValueError('도킹 벽 입력이 유한하지 않습니다.')
    translation, _, rank, _ = np.linalg.lstsq(normals, distances, rcond=None)
    if rank != 2:
        raise ValueError('앞뒤·좌우 위치를 구분할 벽 방향이 부족합니다.')
    matrix = np.asarray(odom_from_base, dtype=float)
    if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
        raise ValueError('도킹 odom 변환 오류')
    xy = matrix[:2, :2] @ translation + matrix[:2, 3]
    heading = math.atan2(matrix[1, 0], matrix[0, 0]) + yaw
    return dict(x=float(xy[0]), y=float(xy[1]), yaw=math.remainder(heading, math.tau),
                forward_error_m=float(translation[0]), lateral_error_m=float(translation[1]),
                heading_error_rad=yaw)


class DockWallTracker:
    """한 scan의 선택 벽 관측을 기존 추적기로 검증하고 도킹 목표로 조립한다."""

    def __init__(self, config: dict) -> None:
        references = config['reference']['walls']
        # 미지정 시 기존 세 벽 계약을 유지한다. 실물 선택은 설정에서만 바꾼다.
        names = config.get('observation_walls', ('rear', 'left', 'right'))
        self._references = {name: references[name] for name in names}
        self._trackers = {name: WallTracker(dict(config['observation'], **wall['observation']))
                          for name, wall in self._references.items()}

    def observe(self, record: dict) -> dict:
        values = {name: tracker.observe(record) for name, tracker in self._trackers.items()}
        result = docking_target(values, self._references, record['odom_from_base'])
        result.update(stamp_ns=int(record['stamp_ns']), ready=all(v['ready'] for v in values.values()),
                      walls=values)
        return result
