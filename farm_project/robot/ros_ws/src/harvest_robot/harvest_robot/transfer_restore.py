"""윈도우 복귀 기준과 경로 계산. 실행·취소·정지는 기존 Navigator가 담당한다."""
from dataclasses import dataclass
from collections.abc import Callable
from typing import Protocol, Any
import math
import uuid
import numpy as np
from numpy.typing import NDArray
from farm_navigation.arrival import measure_arrival, positive_number
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import ArcSpec, arc_path, wrap


class PoseLookup(Protocol):
    def lookup(self, target: str, source: str, stamp_ns: int,
               check: Callable[[], None]) -> NDArray[np.float64]: ...


def _pose(matrix: NDArray[np.float64]) -> tuple[float, float, float]:
    """PoseProvider의 유한한 강체변환에서 평면 자세를 추출한다."""
    m = np.asarray(matrix, dtype=float)
    if (m.shape != (4, 4) or not np.isfinite(m).all()
            or not np.allclose(m[3], (0., 0., 0., 1.), atol=1e-8, rtol=0)
            or not np.allclose(m[:3, :3].T @ m[:3, :3], np.eye(3), atol=1e-6, rtol=0)
            or not math.isclose(float(np.linalg.det(m[:3, :3])), 1., abs_tol=1e-6)
            or math.hypot(m[0, 0], m[1, 0]) < 1e-8):
        raise ValueError('복귀 기준 TF는 유효한 강체변환이어야 합니다.')
    return float(m[0, 3]), float(m[1, 3]), math.atan2(m[1, 0], m[0, 0])


@dataclass(frozen=True)
class RestoreReference:
    """이동 전 정지 시각의 기준. session_id는 odom 재시작마다 달라야 한다."""
    map_id: str
    window_id: str
    session_id: str
    map_frame: str
    odom_frame: str
    base_frame: str
    stamp_ns: int
    window_xy: tuple[float, float]
    heading_map: tuple[float, float]
    arc_origin_odom: tuple[float, float, float]
    arc_spec: ArcSpec

    def __post_init__(self) -> None:
        if not isinstance(self.arc_spec, ArcSpec):
            raise ValueError('출발 곡선 설정 필요')
        for name in ('map_id', 'window_id', 'session_id', 'map_frame', 'odom_frame', 'base_frame'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or any(c.isspace() for c in value):
                raise ValueError(name + ': 비어 있지 않은 식별자 필요')
        if len({self.map_frame, self.odom_frame, self.base_frame}) != 3:
            raise ValueError('map/odom/base 좌표계는 서로 달라야 합니다.')
        if type(self.stamp_ns) is not int or self.stamp_ns <= 0:
            raise ValueError('정지 확인 시각은 양의 ROS ns여야 합니다.')
        for name, size in (('window_xy', 2), ('heading_map', 2), ('arc_origin_odom', 3)):
            value = getattr(self, name)
            if (type(value) is not tuple or len(value) != size or
                    not all(type(v) in (int, float) and math.isfinite(v) for v in value)):
                raise ValueError(name + ': 유한한 좌표 tuple 필요')
        if not math.isclose(math.hypot(*self.heading_map), 1., abs_tol=1e-8, rel_tol=0):
            raise ValueError('저장 방향은 map 기준 단위벡터여야 합니다.')

    @classmethod
    def capture(cls, poses: PoseLookup, *, map_id: str, window_id: str,
                session_id: str, window_xy: tuple[float, float], stamp_ns: int, arc_spec: ArcSpec,
                check: Callable[[], None], map_frame: str = 'map',
                odom_frame: str = 'odom', base_frame: str = 'base_footprint') -> 'RestoreReference':
        """정지 확인 후 곡선 출발 전에 호출. 동일 시각의 map·odom 자세를 저장한다."""
        if type(stamp_ns) is not int or stamp_ns <= 0:
            raise ValueError('최신 TF(0)가 아닌 정지 확인 시각 필요')
        check()
        map_pose = _pose(poses.lookup(map_frame, base_frame, stamp_ns, check))
        odom_pose = _pose(poses.lookup(odom_frame, base_frame, stamp_ns, check))
        check()
        return cls(map_id, window_id, session_id, map_frame, odom_frame, base_frame,
                   stamp_ns, window_xy, (math.cos(map_pose[2]), math.sin(map_pose[2])), odom_pose, arc_spec)

    def require_context(self, map_id: str, window_id: str, session_id: str) -> None:
        """다른 작업·지도·odom 세션의 기록을 복귀에 사용하지 않는다."""
        if (map_id, window_id, session_id) != (self.map_id, self.window_id, self.session_id):
            raise ValueError('복귀 기준의 지도·윈도우·odom 세션 불일치')

    def return_arc(self) -> RoutePlan:
        """기존 곡선 계산의 역순. 차체 방향에 pi를 더하지 않는 전진 우회전이다."""
        path = tuple(reversed(arc_path(self.arc_origin_odom, self.arc_spec)))
        distance = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(path, path[1:]))
        return RoutePlan(uuid.uuid4().hex, '', self.odom_frame,
                         tuple((p[0], p[1]) for p in path), (), distance,
                         tuple(p[2] for p in path))

    def check_reentry(self, current_odom: tuple[float, float, float],
                      heading_limit: float = math.pi / 180, *,
                      position_limit: float | None = None) -> dict[str, float]:
        """벽 이탈 후 원호 시작 자세 확인. 이 함수는 보정 회전이나 이동을 요청하지 않는다."""
        positive_number(heading_limit, '재진입 방향 허용오차')
        limit = self.arc_spec.endpoint_tolerance if position_limit is None else position_limit
        positive_number(limit, '재진입 위치 허용오차')
        if limit > self.arc_spec.deviation:
            raise ValueError('재진입 위치 허용오차는 실행 중 경로 이탈 한계 이하여야 합니다.')
        if len(current_odom) != 3 or not all(math.isfinite(v) for v in current_odom):
            raise ValueError('유효한 현재 odom 자세 필요')
        target = arc_path(self.arc_origin_odom, self.arc_spec)[-1]
        distance = math.hypot(current_odom[0]-target[0], current_odom[1]-target[1])
        angle = abs(wrap(current_odom[2]-target[2]))
        if distance > limit or angle > heading_limit:
            raise RuntimeError('복귀 원호 재진입 위치·방향 오차 초과 '
                f'(위치={distance:.6f}m/한계={limit:.6f}m, '
                f'방향={angle:.6f}rad/한계={heading_limit:.6f}rad)')
        return {'position_error_m': distance, 'heading_error_rad': angle}

    def arrival_validator(self, poses: PoseLookup, *, map_id: str, window_id: str,
                          session_id: str, position_limit: float = .02,
                          heading_limit: float = math.pi / 180
                          ) -> Callable[[int, Callable[[], None]], dict[str, Any]]:
        """Navigator.arrival_validator용. 최종 정지 시각에 윈도우·저장 방향을 검사한다."""
        self.require_context(map_id, window_id, session_id)
        positive_number(position_limit, '복귀 위치 허용오차')
        positive_number(heading_limit, '복귀 방향 허용오차')
        target_yaw = math.atan2(self.heading_map[1], self.heading_map[0])

        def validate(stamp_ns: int, check: Callable[[], None]) -> dict[str, Any]:
            if type(stamp_ns) is not int or stamp_ns <= self.stamp_ns:
                raise RuntimeError('복귀 정지 시각이 출발 기준보다 새롭지 않습니다.')
            check()
            matrix = poses.lookup(self.map_frame, self.base_frame, stamp_ns, check)
            _, _, yaw = _pose(matrix)
            result = measure_arrival(matrix, self.window_xy, target_yaw, position_limit, heading_limit)
            current = (math.cos(yaw), math.sin(yaw))
            dot = current[0]*self.heading_map[0] + current[1]*self.heading_map[1]
            cross = current[0]*self.heading_map[1] - current[1]*self.heading_map[0]
            result.update(window_id=self.window_id, map_id=self.map_id,
                          heading_correction_rad=math.atan2(cross, dot))
            check()
            return result
        return validate
