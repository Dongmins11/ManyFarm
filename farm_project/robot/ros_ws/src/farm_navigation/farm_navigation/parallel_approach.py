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
                  goal: tuple, position_limit: float, heading_limit: float) -> RoutePlan:
    """차체 방향·횡오차를 별도로 검사하고 전방 목표의 추종 경로를 만든다."""
    direction = (math.cos(corridor['yaw']), math.sin(corridor['yaw']))
    delta = (goal[0]-xy[0], goal[1]-xy[1])
    lateral = abs(delta[0]*direction[1]-delta[1]*direction[0])
    forward = delta[0]*direction[0]+delta[1]*direction[1]
    if (abs(math.remainder(yaw-corridor['yaw'], 2*math.pi)) > heading_limit
            or lateral > position_limit or forward <= 1e-9):
        raise RuntimeError('APPROACH_RECOVERY_REQUIRED: 평행 구간에서 방향/횡오차/전방 조건 불충족. 넓은 진입부에서 재정렬 필요')
    # 목표선 각도는 가까운 목표에서 커지므로 차체 정렬 기준으로 사용하지 않는다.
    # 허용 횡오차의 실제 보정·충돌 검사·최종 방향 정렬은 기존 FollowPath가 수행한다.
    return replace(template, points=(tuple(xy), tuple(goal)), distance_m=math.dist(xy, goal), edge_ids=())
