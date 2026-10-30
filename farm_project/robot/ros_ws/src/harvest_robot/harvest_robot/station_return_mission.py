"""수확 복귀 미션. 환경 좌표·장치·준비·정지 정책은 조립자가 전달한다."""
from __future__ import annotations

import math
import time
from typing import Any, Callable
from farm_navigation.route import reverse_plan
from .corridor_navigation import contains


def tag_section(corridors: dict, xy: tuple[float, float], yaw: float,
                position_tolerance_m: float, heading_tolerance_rad: float) -> str | None:
    """후진 속도 부호와 무관하게 실측 차체 방향과 기존 작업 선분으로 태그 구역을 선택한다."""
    matches = [name for name, corridor in corridors.items()
               if contains(corridor, xy, position_tolerance_m)
               and abs(math.remainder(yaw-corridor['yaw'], 2*math.pi)) <= heading_tolerance_rad]
    return matches[0] if len(matches) == 1 else None


def reverse_control_error(message: str) -> bool:
    """후진 플러그인의 충돌 예측만 기존 NO_VALID_CONTROL 재시도 대상으로 분류한다."""
    value = message.strip().lower()
    return (not value or 'collision ahead' in value
            or value in ('collision on reverse route', 'collision on reverse heading alignment'))


class StationReturnMission:
    """준비·경로·태그 수명을 조정한다. Action 응답과 상태 전환은 소유하지 않는다."""

    def __init__(self, *, prepare: Callable[[], None], check: Callable[[], None],
                 navigator: Any, graph: Any, station: Any, poses: Any, settings: Any,
                 tag_control: Any, corridors: dict, docking: Any = None) -> None:
        self._prepare, self._cancel_check = prepare, check
        self._navigator, self._graph, self._station = navigator, graph, station
        self._poses, self._settings = poses, settings
        self._tag_control, self._corridors = tag_control, corridors
        self._docking = docking
        self._docked = False
        self._tag_active = False
        self._section: str | None = None
        self._next_update = 0.
        self._navigating = False

    def prepare(self) -> None:
        self._cancel_check()
        self._prepare()
        self._cancel_check()
        self._navigator.preflight_navigation()

    def navigate(self) -> None:
        self._cancel_check()
        current = self._poses.current(self._cancel_check)
        forward = self._graph.plan(self._station.xy,
            (float(current[0, 3]), float(current[1, 3])),
            self._settings.max_goal_distance_m, self._settings.max_start_distance_m)
        plan = reverse_plan(forward)
        self._navigating = True
        self.check()
        self._navigator.navigate(self._station.xy, self._station.yaw,
                                 route_plan=plan, reverse=True)
        self._cancel_check()

    @property
    def docked(self) -> bool:
        return self._docked

    @property
    def docking_enabled(self) -> bool:
        return self._docking is not None

    def dock(self) -> None:
        """그래프 도착 뒤 태그 세션을 닫고 벽 기준 도킹으로 전환한다."""
        self._navigating = False
        if self._tag_active:
            self._tag_control.end()
            self._tag_active, self._section = False, None
        self._cancel_check()
        self._docking.execute()
        self._cancel_check()
        self._docked = True

    def check(self) -> None:
        """취소는 매번 확인한다. 태그는 구역 안에서 토큰을 유지하며 0.2초마다 위치를 확인한다."""
        self._cancel_check()
        if not self._navigating or self._tag_control is None or time.monotonic() < self._next_update:
            return
        self._next_update = time.monotonic() + .2
        current = self._poses.current(self._cancel_check)
        xy = (float(current[0, 3]), float(current[1, 3]))
        yaw = math.atan2(current[1, 0], current[0, 0])
        matches = [name for name, corridor in self._corridors.items()
                   if contains(corridor, xy, self._settings.max_start_distance_m)]
        # 같은 작업 구역에서는 방향 정렬 때문에 세션을 다시 만들지 않는다.
        section = (self._section if self._tag_active and matches == [self._section]
                   else tag_section(self._corridors, xy, yaw,
                                    self._settings.max_start_distance_m,
                                    self._settings.heading_tolerance_rad))
        if self._tag_active and section != self._section:
            self._tag_control.end()
            self._tag_active = False
            self._section = None
            # 종료와 새 시작을 같은 호출에서 연속 발행하지 않는다. 주행은 계속한다.
            return
        if section is not None and not self._tag_active:
            self._tag_control.begin(section)
            self._tag_active, self._section = True, section

    def cleanup(self) -> None:
        """성공·실패·취소 모두 태그를 닫고 기존 Navigator의 취소·정지 확인을 수행한다."""
        self._navigating = False
        try:
            if self._tag_active:
                self._tag_control.end()
        finally:
            self._tag_active, self._section = False, None
            try:
                if self._docking is not None:
                    self._docking.cleanup()
            finally:
                self._navigator.cancel_nav()


