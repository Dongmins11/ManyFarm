from .mission_state import MissionState


class IdleState(MissionState):
    name = 'IDLE'

    def enter(self) -> None:
        super().enter()
        # 작업 접수는 Communication → Mission → Controller 경로로 들어옵니다.
        # 이 상태 자체는 주행이나 관측을 시작하지 않습니다.
