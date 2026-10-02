"""State는 행동을 시작하고 완료 알림으로 전환을 요청합니다. execute 루프는 없습니다."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scout_mission import ScoutMission
    from ..scout_state_controller import ScoutStateController


class MissionState:
    name = 'BASE'

    def __init__(self, mission: ScoutMission, controller: ScoutStateController) -> None:
        self._mission: ScoutMission = mission
        self._controller: ScoutStateController = controller
        self._active: bool = False  # exit 이후 늦은 완료 알림은 사용하지 않습니다.

    @property
    def active(self) -> bool:
        return self._active

    def enter(self) -> None:
        """단계의 시작점. 요청 후 반환하며 결과를 여기서 기다리지 않습니다."""
        self._active = True

    def exit(self) -> None:
        """콜백의 유효 범위를 종료합니다. 정상 전환마다 이동을 취소하지 않습니다."""
        self._active = False

    def on_stop_requested(self) -> None:
        """공통 중단 통지. 실제 이동/워커 중단 확인은 Controller가 조율합니다."""
        # 기본 상태에는 별도의 장치 소유권이 없습니다.
        # 상태가 자체 구독을 추가할 경우 여기서 중단을 요청하고 exit에서 해제합니다.
        pass
