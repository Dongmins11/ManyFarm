"""Confluence DOCKING에 대응. 실제 도킹 계약 연결 전에는 진입을 거절합니다."""
from .mission_state import MissionState


class DockingState(MissionState):
    name = 'DOCKING'

    def enter(self) -> None:
        super().enter()
        # Nav2로 Station에 도착한 것만으로 정밀 도킹 성공을 만들지 않습니다.
        raise RuntimeError('DOCKING_UNAVAILABLE: return_to_station 및 정밀 도킹 연결이 필요합니다.')
