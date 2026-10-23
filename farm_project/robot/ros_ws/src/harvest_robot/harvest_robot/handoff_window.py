"""역원호 뒤 window 최종 보정. 현재 방향의 짧은 전진만 허용한다.

큰 횡오차·후진 필요·TF 변화는 자동 우회하지 않는다. 경로와 최종 map 판정을
분리하고, 기존 Navigator의 충돌 검사·실제 정지 확인을 재사용한다.
"""
import math
import uuid
import numpy as np
from farm_navigation.arc_isolation import CommandGate
from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import wrap
from .handoff_navigation import NavigationStep
from .transfer_restore import _pose


class WindowCommandGate(CommandGate):
    """전진 0.01m/s, 각속도 절댓값 0.03rad/s 전용 출력 제한."""
    def __init__(self) -> None:
        super().__init__(direction='retreat')

    def accept(self, linear: float, angular: float, now: float, conflict: bool = False) -> bool:
        return super().accept(-linear, angular, now,
            conflict=conflict or abs(angular) > .030000001)


def correction_path(current: tuple, window: tuple, *, position_limit: float = .02) -> tuple:
    """map 기준 전진 투영 경로. 끝점 3mm 오차를 포함해 2cm 안쪽 여유를 둔다."""
    if not all(math.isfinite(v) for v in (*current, *window, position_limit)) or position_limit <= 0:
        raise ValueError('WINDOW_INPUT: 유한한 자세·양의 허용오차 필요')
    dx, dy = window[0]-current[0], window[1]-current[1]
    if math.hypot(dx, dy) <= position_limit:
        return current, current, True
    c, s = math.cos(current[2]), math.sin(current[2])
    along, cross = dx*c+dy*s, -dx*s+dy*c
    if not .003 < along <= .06 or abs(cross) > min(.015, position_limit-.005):
        raise RuntimeError('WINDOW_REALIGN_REQUIRED: 짧은 전진으로 window 완료범위 확보 불가 '
                           f'(전방={along:.4f}m, 횡오차={cross:.4f}m)')
    return current, (current[0]+along*c, current[1]+along*s, current[2]), False


def plan_window(reference, poses, motion, inputs, guard, policy, check) -> NavigationStep:
    """정지 상태의 동일 시각 map/odom 변환으로 보정 경로를 한 번 구성한다."""
    motion.wait_stopped(check)
    def stopped() -> None:
        check()
        reference.require_context(*inputs.context())
        if not motion.stationary_now():
            raise RuntimeError('WINDOW_NOT_STOPPED: 보정 계획 중 정지 상실')
    stamp, matrices = poses.lookup_available_pair((reference.map_frame, reference.odom_frame),
        reference.base_frame, inputs.odom_stamp, stopped)
    stopped()
    map_base, odom_base = matrices
    current = _pose(map_base)
    heading = math.atan2(reference.heading_map[1], reference.heading_map[0])
    if abs(wrap(current[2]-heading)) > policy.return_heading:
        raise RuntimeError('WINDOW_HEADING: 저장 작업 방향 허용범위 초과')
    start, end, skip = correction_path(current, reference.window_xy, position_limit=policy.return_position)
    odom_map = odom_base @ np.linalg.inv(map_base)
    odom_start = _pose(odom_base)
    endpoint = odom_map @ np.array([end[0], end[1], 0., 1.])
    length = math.dist(start[:2], end[:2])
    count = max(1, math.ceil(length/.002))
    path = tuple((odom_start[0]+(endpoint[0]-odom_start[0])*i/count,
                  odom_start[1]+(endpoint[1]-odom_start[1])*i/count, odom_start[2])
                 for i in range(count+1))
    route = RoutePlan(uuid.uuid4().hex, '', reference.odom_frame,
        tuple(p[:2] for p in path), (), length, tuple(p[2] for p in path))
    live = guard('window', path, check)
    validator = reference.arrival_validator(poses, map_id=reference.map_id,
        window_id=reference.window_id, session_id=reference.session_id,
        position_limit=policy.return_position, heading_limit=policy.return_heading)
    def monitor() -> None:
        reference.require_context(*inputs.context())
        live()
        at = inputs.odom_stamp()
        a = poses.lookup(reference.map_frame, reference.base_frame, at, check)
        b = poses.lookup(reference.odom_frame, reference.base_frame, at, check)
        transform = b @ np.linalg.inv(a)
        delta = _pose(transform @ np.linalg.inv(odom_map))
        if math.hypot(*delta[:2]) > .005 or abs(delta[2]) > math.radians(1):
            raise RuntimeError('WINDOW_TF_CHANGED: 보정 중 map/odom 변환 변경')
        pose = _pose(b)
        c, s = math.cos(odom_start[2]), math.sin(odom_start[2])
        dx, dy = pose[0]-odom_start[0], pose[1]-odom_start[1]
        if (abs(-dx*s+dy*c) > .005 or not -.003 <= dx*c+dy*s <= length+.008
                or abs(wrap(pose[2]-odom_start[2])) > policy.return_heading):
            raise RuntimeError('WINDOW_PATH_DEVIATION: 보정 경로 이탈')
    def validate(at: int, stopped_check) -> dict:
        reference.require_context(*inputs.context())
        return validator(at, stopped_check)
    return NavigationStep(route, odom_start[2], validate, monitor, stationary_only=skip)
