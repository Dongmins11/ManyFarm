"""정밀주행 미활성 환경의 기본 포트. 센서 알고리즘은 farm_docking에 둔다."""
from typing import Protocol
from .mission_types import Request


class DockingPort(Protocol):
    def available(self) -> bool: ...
    def tag(self, request: Request) -> bool: ...
    def dock(self, request: Request) -> bool: ...
    def clear(self, request: Request) -> bool: ...
    def stop(self) -> None: ...


class UnavailableDocking:
    @property
    def pending(self) -> bool:
        """이 포트는 정밀주행 Goal을 만들지 않는다."""
        return False

    def available(self) -> bool:
        return False

    def dock(self, request: Request) -> bool:
        raise RuntimeError('정밀주행이 비활성 또는 미연결 상태입니다.')

    def tag(self, request: Request) -> bool:
        raise RuntimeError('정밀주행 미연결')

    def clear(self, request: Request) -> bool:
        raise RuntimeError('정밀주행 미연결')

    def stop(self) -> None:
        # 시작 가능한 구동기가 없다. 성공/도킹 상태를 만들지 않는다.
        return None
