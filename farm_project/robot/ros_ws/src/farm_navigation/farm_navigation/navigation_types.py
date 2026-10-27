"""로봇 종류와 무관한 주행 입력·결과. 거리 m, 각도 rad, 시각 ROS ns."""
from __future__ import annotations
from dataclasses import dataclass, fields
from typing import Any
import math


@dataclass(frozen=True)
class NavigationSettings:
    # 연결 이름은 Node namespace를 따르는 상대 이름을 기본으로 사용합니다.
    mode: str = 'navigate_to_pose'
    map_frame: str = 'map'
    base_frame: str = 'base_footprint'
    odom_topic: str = 'odom'
    navigate_action: str = 'navigate_to_pose'
    follow_action: str = 'follow_path'
    controller_node: str = 'controller_server'
    controller_id: str = 'FollowPath'
    goal_checker_id: str = 'goal_checker'
    progress_checker_id: str = 'progress_checker'
    # 주행 제한은 sim에서 ROS 시간, real에서 단조 실시간. I/O 제한은 항상 실시간이다.
    goal_timeout_s: float = 300.0
    response_timeout_s: float = 15.0
    cancel_timeout_s: float = 10.0
    readiness_timeout_s: float = 60.0
    tf_timeout_s: float = 3.0
    tf_max_age_s: float = 1.0
    arrival_tolerance_m: float = .08
    heading_tolerance_rad: float = .12
    settle_s: float = .8
    settle_timeout_s: float = 20.0
    odom_max_age_s: float = .5
    stopped_linear_mps: float = .005
    stopped_angular_rps: float = .02
    max_start_distance_m: float = .10
    max_goal_distance_m: float = .02
    path_spacing_m: float = .04
    parallel_approach: bool = False
    collision_retry_count: int = 0
    tf_recovery_enabled: bool = False
    tf_recovery_timeout_s: float = 10.0

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> NavigationSettings:
        known = {f.name for f in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f'알 수 없는 주행 설정: {sorted(unknown)}')
        settings = cls(**values)
        if settings.mode not in ('navigate_to_pose', 'follow_path'):
            raise ValueError('navigation.mode: navigate_to_pose 또는 follow_path 필요')
        for f in fields(settings):
            value = getattr(settings, f.name)
            if isinstance(f.default, float):
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                    raise ValueError(f'{f.name}: 양의 유한한 수 필요')
            elif isinstance(f.default, bool):
                if not isinstance(value, bool):
                    raise ValueError(f'{f.name}: bool 필요')
            elif isinstance(f.default, int):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{f.name}: 0 이상의 정수 필요')
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f'{f.name}: 비어 있지 않은 문자열 필요')
        if settings.settle_timeout_s <= settings.settle_s:
            raise ValueError('settle_timeout_s는 settle_s보다 커야 합니다.')
        return settings


@dataclass(frozen=True)
class RoutePlan:
    plan_id: str
    graph_revision: str  # 파일 내용 SHA256. 향후 경로/허가 버전 대조에 사용 가능
    frame_id: str
    points: tuple[tuple[float, float], ...]
    edge_ids: tuple[str, ...]  # 경유 순서이며 현재 점유/진입 허가를 뜻하지 않습니다.
    distance_m: float


@dataclass(frozen=True)
class NavigationStatus:
    request_id: str = ''
    phase: str = 'IDLE'
    plan_id: str = ''
    detail: str = ''


@dataclass(frozen=True)
class NavigationResult:
    request_id: str
    plan_id: str
    stamp_ns: int  # 도착 후 정지 확인에 사용한 odom 시각
    measurement: dict[str, Any]
