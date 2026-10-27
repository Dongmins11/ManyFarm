"""State.enter는 I/O 요청 후 반환하고 완료는 Controller에서 전달한다."""
from typing import Any


class MissionState:
    name = 'IDLE'
    def __init__(self, controller: Any) -> None:
        self.controller = controller
    def enter(self) -> None:
        pass
    def exit(self) -> None:
        pass
