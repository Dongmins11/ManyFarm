"""환경의 기존 복귀 경로와 수확 Mission/Controller를 연결한다."""
from __future__ import annotations

import json
import math
from typing import Any
from geometry_msgs.msg import Twist
from farm_common.station_return import StationReturn, plan_station_return
from farm_navigation.operation_clock import operation_time
from .station_return_mission import StationReturnMission
from .station_return_states import ReturnController


class ComponentStationReturn(StationReturn):
    """Action 수명은 공통 서버, 작업 단계·태그 수명은 전달받은 수확 컴포넌트가 담당한다."""

    def __init__(self, node: Any, *, recovery_output: Any = None, **kwargs: Any) -> None:
        self._mission = self._controller = None
        self._recovery_output = recovery_output
        super().__init__(node, **kwargs)
        if self._settings.collision_retry_count:
            if recovery_output is None:
                raise ValueError('복귀 재시도는 기존 출력 소유자 연결이 필요합니다.')
            for client in (self._client, self._forward_client):
                if client is not None:
                    client.set_recovery_stop(self._stop_for_recovery)

    def _check(self) -> None:
        if self._mission is None:
            self._cancel_check()
        else:
            self._mission.check()

    def _stop_for_recovery(self) -> None:
        """실물 어댑터와 같은 소유권 검사 후 기존 출력으로 정지만 발행한다."""
        output = self._recovery_output
        with output.lock:
            self._cancel_check()
            if self._handoff.current != ('return', self._handle.request.task_id) or output.error:
                raise RuntimeError('복귀 재시도 출력 소유권 상실')
            output.publisher.publish(Twist())

    def _plan_return(self, current: Any) -> tuple:
        """기존 승인된 전진/후진 선택과 스테이션 최종 방향을 유지한다."""
        plan, reverse, audit = plan_station_return(self._graph, self._station,
            (float(current[0, 3]), float(current[1, 3])),
            math.atan2(current[1, 0], current[0, 0]), self._settings)
        self._node.get_logger().info('STATION_RETURN_PLAN: '+json.dumps(audit, ensure_ascii=False))
        return self._navigator if reverse else self._forward_navigator, plan, reverse

    def _run_mission(self) -> None:
        self._mission = StationReturnMission(
            prepare=lambda: self._prepare(self._cancel_check) if self._prepare else None,
            check=self._cancel_check, navigator=self._navigator, graph=self._graph,
            station=self._station, poses=self._poses, settings=self._settings,
            tag_control=self._tag_control,
            corridors=self._node.section_resolution.get('corridors', {}),
            plan_return=self._plan_return, clock=lambda: operation_time(self._node))
        self._controller = ReturnController(self._mission)
        self._controller.run()
        self._cancel_check()

    def _cleanup_mission(self) -> None:
        try:
            if self._controller is None:
                super()._cleanup_mission()
            elif self._controller.cleanup_error is not None:
                raise self._controller.cleanup_error
        finally:
            self._mission = self._controller = None
