"""환경 그래프가 지정한 직선 작업 구간의 진입·진행 방향 검사. 좌표는 데이터에서 읽는다."""
import math
from dataclasses import replace
from .route import project
from .navigation_types import RoutePlan


def select_corridor(corridors: list, goal: tuple, yaw: float, tolerance: float) -> dict:
    matches = [c for c in corridors if project(goal, c['entry'], c['exit'])[0] < 1e-5
               and abs(math.remainder(yaw-c['yaw'], 2*math.pi)) <= tolerance]
    if len(matches) != 1:
        raise ValueError('평행 접근 목표에 대응하는 직선 작업 구간/방향이 없습니다.')
    return matches[0]


def inside_corridor(corridor: dict, xy: tuple, margin: float) -> bool:
    a, b = corridor['entry'], corridor['exit']
    dx, dy = b[0]-a[0], b[1]-a[1]
    ratio = ((xy[0]-a[0])*dx+(xy[1]-a[1])*dy)/(dx*dx+dy*dy)
    return 0 < ratio < 1 and project(xy, a, b)[0] <= margin


def straight_plan(template: RoutePlan, corridor: dict, xy: tuple, yaw: float,
                  goal: tuple, position_limit: float, heading_limit: float, *,
                  path_heading_limit: float | None = None) -> RoutePlan:
    """정렬된 차체에서 전방 목표로만 진행한다. 좁은 구간 후진/제자리 회전은 요청하지 않는다."""
    direction = (math.cos(corridor['yaw']), math.sin(corridor['yaw']))
    delta = (goal[0]-xy[0], goal[1]-xy[1])
    lateral = abs(delta[0]*direction[1]-delta[1]*direction[0])
    forward = delta[0]*direction[0]+delta[1]*direction[1]
    # 미지정 호출자는 기존 각도 기준을 유지한다.
    path_limit = heading_limit if path_heading_limit is None else path_heading_limit
    if (isinstance(path_limit, bool) or not isinstance(path_limit, (int, float))
            or not math.isfinite(path_limit) or not 0 < path_limit < math.pi / 2):
        raise ValueError('path_heading_limit는 0~pi/2 사이의 유한한 각도여야 합니다.')
    heading_error = abs(math.remainder(yaw-corridor['yaw'], 2*math.pi))
    path_angle = abs(math.atan2(lateral, forward))
    failed = []
    if heading_error > heading_limit: failed.append('body_heading')
    if lateral > position_limit: failed.append('lateral')
    if forward <= 0: failed.append('not_ahead')
    if path_angle > path_limit: failed.append('path_heading')
    if failed:
        raise RuntimeError(
            'APPROACH_RECOVERY_REQUIRED: ' + ','.join(failed)
            + f'; current_xy={xy}, goal_xy={goal}, forward_m={forward:.6f}'
            + f', lateral_m={lateral:.6f}/{position_limit:.6f}'
            + f', body_heading_rad={heading_error:.6f}/{heading_limit:.6f}'
            + f', path_heading_rad={path_angle:.6f}/{path_limit:.6f}')
    return replace(template, points=(tuple(xy), tuple(goal)), distance_m=math.dist(xy, goal), edge_ids=())
