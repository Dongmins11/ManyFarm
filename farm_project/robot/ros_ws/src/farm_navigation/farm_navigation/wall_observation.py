"""공통 벽 분석 결과를 고정 좌표로 변환하는 읽기 전용 어댑터."""
from __future__ import annotations
import math
import numpy as np
from .wall_reference import scan_points, fit_wall


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
        wall = fit_wall(scan_points(record, tuple(c['sector_deg'])),
                        threshold_m=c['fit_threshold_m'], min_points=c['min_points'],
                        min_ratio=c['min_ratio'], min_span_m=c['min_span_m'])
        if wall['residual_rms_m'] > c['max_rms_m']:
            raise ValueError('벽 직선 잔차 초과')
        if not c['min_distance_m'] <= wall['distance_m'] <= c['max_distance_m']:
            raise ValueError('벽 거리 범위 초과')
        if abs(wall['normal_angle_rad']) > c['max_angle_rad']:
            raise ValueError('전방 벽 각도 범위 초과')
        matrix = np.asarray(record['odom_from_base'], dtype=float)
        if matrix.shape != (4,4) or not np.isfinite(matrix).all():
            raise ValueError('고정 프레임 변환 오류')
        # 평면 운동만 지원. 기울어진 TF를 조용히 2D로 투영하지 않는다.
        if np.max(np.abs(matrix[2,:2])) > .01 or abs(matrix[2,2]-1) > .01:
            raise ValueError('평면 밖 차체 자세')
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
            raise ValueError('벽 관측 간격 초과')
        self.last=result
        if self.anchor is None:self.anchor=result
        self.count += 1
        result['ready']=self.count>=c['stable_frames']
        return result
