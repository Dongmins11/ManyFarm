"""성공한 경로 계산 함수의 연결. 새 제어식·실물 좌표를 추가하지 않는다."""
from dataclasses import replace
import math
import uuid

from farm_navigation.navigation_types import RoutePlan
from farm_navigation.transfer_arc import arc_path, wrap
from .transfer_retreat import RetreatPlan, retreat_plan, alignment_path
from .transfer_restore import RestoreReference


def departure_route(reference: RestoreReference) -> RoutePlan:
    """저장한 출발 자세와 기존 arc_path로 후진 좌회전 경로를 만든다."""
    path = arc_path(reference.arc_origin_odom, reference.arc_spec)
    return RoutePlan(uuid.uuid4().hex, '', reference.odom_frame,
        tuple(p[:2] for p in path), (),
        sum(math.dist(a[:2], b[:2]) for a, b in zip(path, path[1:])),
        tuple(p[2] for p in path))


def return_route(reference: RestoreReference) -> RoutePlan:
    """기존 복귀 함수의 역원호를 그대로 사용한다."""
    return reference.return_arc()


def retreat_route(reference: RestoreReference, current: tuple,
                  **limits: float) -> RetreatPlan:
    """기존 이탈 계산을 사용하고 선택한 odom 프레임을 유지한다."""
    target = arc_path(reference.arc_origin_odom, reference.arc_spec)[-1]
    plan = retreat_plan(current, target, **limits)
    return replace(plan, route=replace(plan.route, frame_id=reference.odom_frame))


def alignment(reference: RestoreReference, current: tuple) -> tuple[float, tuple]:
    """기존 footprint 검사에 전달할 회전 자세열과 상대 회전각을 반환한다."""
    target_yaw = arc_path(reference.arc_origin_odom, reference.arc_spec)[-1][2]
    path = alignment_path(current, target_yaw)
    return wrap(target_yaw-current[2]), path
