"""공통 도착 오차·Nav2 Goal checker 검사. 기준값은 호출자가 지정합니다."""
import math
from typing import Any
from collections.abc import Sequence
import numpy as np
from numpy.typing import NDArray
from .navigation_types import NavigationSettings


class NavigationConfigurationError(RuntimeError):
    """주행 Goal checker가 요청한 도착 조건을 만족할 수 없습니다."""


def positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NavigationConfigurationError(f'{name}: expected a positive finite number, got {value!r}')
    if not math.isfinite(value) or value <= 0:
        raise NavigationConfigurationError(f'{name}: expected a positive finite number, got {value!r}')
    return float(value)


def validate_goal_checkers(
    parameters: dict[str, Any], position_limit: float, heading_limit: float, *,
    stopped_linear_limit: float = NavigationSettings.stopped_linear_mps,
    stopped_angular_limit: float = NavigationSettings.stopped_angular_rps,
) -> list[dict[str, Any]]:
    """Nav2의 도착 기준이 최종 위치·방향·정지 검사보다 느슨하지 않은지 확인합니다.

    NavigateToPose는 실제 선택한 checker ID를 알리지 않으므로 전달된 모든
    checker를 검사합니다. 기존 SimpleGoalChecker 호출 계약도 유지합니다.
    """
    position_limit = positive_number(position_limit, 'arrival_tolerance_m')
    heading_limit = positive_number(heading_limit, 'heading_tolerance_rad')
    ids = parameters.get('goal_checker_plugins')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
        raise NavigationConfigurationError('controller_server.goal_checker_plugins is missing or empty')
    checkers = []
    for checker in ids:
        get = lambda suffix: parameters.get(f'{checker}.{suffix}')
        plugin = get('plugin')
        if plugin not in ('nav2_controller::SimpleGoalChecker', 'nav2_controller::StoppedGoalChecker'):
            raise NavigationConfigurationError(f'{checker}: unsupported goal checker {plugin!r}')
        xy = positive_number(get('xy_goal_tolerance'), f'{checker}.xy_goal_tolerance')
        yaw = positive_number(get('yaw_goal_tolerance'), f'{checker}.yaw_goal_tolerance')
        if xy >= position_limit or yaw >= heading_limit:
            raise NavigationConfigurationError(
                f'Nav2/survey tolerance mismatch: {checker} '
                f'xy={xy:.3f}m, yaw={yaw:.3f}rad; '
                f'Nav2 tolerances must be below survey limits '
                f'xy={position_limit:.3f}m, yaw={heading_limit:.3f}rad. '
                'Update the selected Nav2 configuration and restart navigation. '
                'Configured controller tolerance must be tighter than requested arrival tolerance.')
        if get('symmetric_yaw_tolerance') is True:
            raise NavigationConfigurationError(f'{checker}: symmetric_yaw_tolerance must be false for an exact final heading (including camera direction)')
        checked = {'id': checker, 'xy_goal_tolerance': xy,
                   'yaw_goal_tolerance': yaw, 'stateful': get('stateful')}
        if plugin == 'nav2_controller::StoppedGoalChecker':
            # 위치를 한 번 통과한 뒤 제동 중 벗어난 경우에도 계속 검사해야 합니다.
            if get('stateful') is not False:
                raise NavigationConfigurationError(f'{checker}: StoppedGoalChecker requires stateful=false')
            linear = positive_number(get('trans_stopped_velocity'), f'{checker}.trans_stopped_velocity')
            angular = positive_number(get('rot_stopped_velocity'), f'{checker}.rot_stopped_velocity')
            linear_limit = positive_number(stopped_linear_limit, 'stopped_linear_mps')
            angular_limit = positive_number(stopped_angular_limit, 'stopped_angular_rps')
            if linear > linear_limit or angular > angular_limit:
                raise NavigationConfigurationError(
                    f'{checker}: Nav2 stopped velocities must not exceed navigation limits: '
                    f'trans={linear:.4f}m/s (limit={linear_limit:.4f}m/s), '
                    f'rot={angular:.4f}rad/s (limit={angular_limit:.4f}rad/s)')
            thresholds = []
            for key in ('min_x_velocity_threshold', 'min_y_velocity_threshold', 'min_theta_velocity_threshold'):
                value = parameters.get(key)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0):
                    raise NavigationConfigurationError(
                        f'controller_server.{key}: expected a nonnegative finite number, got {value!r}')
                thresholds.append(float(value))
            # 정지 기준 이상의 운동 전체가 0으로 가려지는 설정을 막습니다.
            # 일부 축만 가려질 때의 원시 속도·지속 정지는 최종 MotionMonitor가 검사합니다.
            if math.hypot(*thresholds[:2]) >= linear or thresholds[2] >= angular:
                raise NavigationConfigurationError(
                    f'{checker}: controller velocity masking thresholds must be below stopped velocities: '
                    f'planar={math.hypot(*thresholds[:2]):.4f}m/s (stopped={linear:.4f}m/s), '
                    f'angular={thresholds[2]:.4f}rad/s (stopped={angular:.4f}rad/s)')
            checked.update(trans_stopped_velocity=linear, rot_stopped_velocity=angular)
        checkers.append(checked)
    return checkers


def measure_arrival(transform: NDArray[np.float64], goal_xy: Sequence[float], goal_yaw: float, position_limit: float, heading_limit: float) -> dict[str, Any]:
    """Measure a timestamped map-to-base transform; headings wrap at +/-pi."""
    x, y = float(transform[0, 3]), float(transform[1, 3])
    yaw = math.atan2(float(transform[1, 0]), float(transform[0, 0]))
    gx, gy, gyaw = float(goal_xy[0]), float(goal_xy[1]), float(goal_yaw)
    if not all(math.isfinite(v) for v in (x, y, yaw, gx, gy, gyaw)):
        raise RuntimeError('Arrival pose contains non-finite coordinates')
    distance = math.hypot(x - gx, y - gy)
    angle = abs(math.atan2(math.sin(yaw - gyaw), math.cos(yaw - gyaw)))
    return {'goal_map': {'x': gx, 'y': gy, 'yaw': gyaw},
            'actual_map': {'x': x, 'y': y, 'yaw': yaw},
            'position_error_m': distance, 'heading_error_rad': angle,
            'position_tolerance_m': float(position_limit),
            'heading_tolerance_rad': float(heading_limit),
            'accepted': distance <= position_limit and angle <= heading_limit}


def arrival_description(measurement: dict[str, Any]) -> str:
    actual, goal = measurement['actual_map'], measurement['goal_map']
    return (f"distance={measurement['position_error_m']:.4f}m "
            f"(limit={measurement['position_tolerance_m']:.4f}m), "
            f"heading={measurement['heading_error_rad']:.4f}rad "
            f"(limit={measurement['heading_tolerance_rad']:.4f}rad); "
            f"goal=({goal['x']:.3f},{goal['y']:.3f},{goal['yaw']:.3f}), "
            f"actual=({actual['x']:.3f},{actual['y']:.3f},{actual['yaw']:.3f})")
