"""선택형 후진 곡선 시험의 순수 계산. SI 단위, 기존 장치/미션에 의존하지 않는다."""
from dataclasses import dataclass
import math


def wrap(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


@dataclass(frozen=True)
class ArcSpec:
    radius: float = 0.10
    angle: float = math.pi / 2
    spacing: float = 0.002
    deviation: float = 0.01
    yaw_tolerance: float = 0.05
    endpoint_tolerance: float = 0.008
    timeout: float = 60.0

    def __post_init__(self) -> None:
        for value in vars(self).values():
            if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
                raise ValueError('설정은 유한한 양수여야 합니다.')
        if not .05 <= self.radius <= .30:
            raise ValueError('시험 반경은 0.05~0.30m입니다.')
        if self.angle > math.pi / 2 or self.spacing > self.radius / 10:
            raise ValueError('시험은 90도 이하, 경로 간격은 반경의 1/10 이하입니다.')
        if self.deviation >= self.radius or self.endpoint_tolerance >= self.radius:
            raise ValueError('허용 오차는 반경보다 작아야 합니다.')


def arc_pose(origin: tuple, radius: float, angle: float) -> tuple:
    """차체 중심을 뒤·오른쪽으로 이동하며 왼쪽으로 회전한다."""
    x, y, yaw = origin
    dx, dy = -radius * math.sin(angle), -radius * (1 - math.cos(angle))
    return (x + math.cos(yaw)*dx - math.sin(yaw)*dy,
            y + math.sin(yaw)*dx + math.cos(yaw)*dy, wrap(yaw + angle))


def arc_path(origin: tuple, spec: ArcSpec) -> list:
    if len(origin) != 3 or not all(math.isfinite(v) for v in origin):
        raise ValueError('유효한 시작 자세 필요')
    count = max(2, math.ceil(spec.radius * spec.angle / spec.spacing))
    return [arc_pose(origin, spec.radius, spec.angle*i/count) for i in range(count+1)]


def measure(origin: tuple, current: tuple, spec: ArcSpec) -> dict:
    if not all(math.isfinite(v) for v in current):
        raise ValueError('유효하지 않은 odom')
    angle = wrap(current[2] - origin[2])
    expected = arc_pose(origin, spec.radius, min(spec.angle, max(0, angle)))
    end = arc_pose(origin, spec.radius, spec.angle)
    return dict(angle=angle, deviation=math.hypot(current[0]-expected[0], current[1]-expected[1]),
                endpoint_error=math.hypot(current[0]-end[0], current[1]-end[1]),
                yaw_error=abs(wrap(current[2]-end[2])))


def check_motion(origin: tuple, current: tuple, spec: ArcSpec) -> dict:
    result = measure(origin, current, spec)
    if result['deviation'] > spec.deviation:
        raise RuntimeError('곡선 경로 위치 오차 초과')
    if not -spec.yaw_tolerance <= result['angle'] <= spec.angle + spec.yaw_tolerance:
        raise RuntimeError('회전 방향 또는 각도 범위 이탈')
    return result


def check_complete(origin: tuple, current: tuple, spec: ArcSpec) -> dict:
    result = check_motion(origin, current, spec)
    if result['endpoint_error'] > spec.endpoint_tolerance or result['yaw_error'] > spec.yaw_tolerance:
        raise RuntimeError('곡선 종료 위치·각도 오차 초과')
    return result


def trial_profile() -> dict:
    """새 ID로만 추가. 기존 RPP/StationReverse/goal checker 수치는 변경하지 않는다."""
    return {
        'TransferArc': {
            'plugin': 'farm_arc_controller::ArcController',
            'desired_linear_vel': 0.01,
            'lookahead_dist': 0.04,
            'min_lookahead_dist': 0.04, 'max_lookahead_dist': 0.04,
            'use_velocity_scaled_lookahead_dist': False,
            'use_rotate_to_heading': False, 'allow_reversing': True,
            'use_collision_detection': True,
            'max_allowed_time_to_collision_up_to_carrot': 2.0,
            'use_regulated_linear_velocity_scaling': True,
            'regulated_linear_scaling_min_speed': 0.003,
            'min_approach_linear_velocity': 0.003,
            'approach_velocity_scaling_dist': 0.04,
            'use_fixed_curvature_lookahead': False,
            'interpolate_curvature_after_goal': False,
            'stateful': False,
        },
        'transfer_arc_goal': {
            'plugin': 'nav2_controller::SimpleGoalChecker',
            'stateful': False, 'xy_goal_tolerance': 0.005,
            'yaw_goal_tolerance': 0.04,
        },
        'transfer_arc_progress': {
            'plugin': 'nav2_controller::PoseProgressChecker',
            'required_movement_radius': 0.01,
            'required_movement_angle': 0.04,
            'movement_time_allowance': 10.0,
        },
    }


def add_profile(parameters: dict) -> dict:
    from copy import deepcopy
    output = deepcopy(parameters)
    controller = output['controller_server']['ros__parameters']
    for key, value in trial_profile().items():
        if key in controller:
            raise ValueError('시험 ID가 이미 존재합니다: ' + key)
        controller[key] = value
    for key, value in [('controller_plugins', 'TransferArc'),
                       ('goal_checker_plugins', 'transfer_arc_goal'),
                       ('progress_checker_plugins', 'transfer_arc_progress')]:
        if value in controller[key]:
            raise ValueError('중복 플러그인 ID')
        controller[key].append(value)
    return output
