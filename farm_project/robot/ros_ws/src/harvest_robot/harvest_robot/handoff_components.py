"""설정된 동작을 조합한다. ROS 서버 설정 변경이나 로봇별 분기는 하지 않는다.

하위 동작은 상위 HarvestHandoffMotion의 단일 작업 스레드에서 실행한다.
시작/결과/취소의 비동기 계약은 상위 객체가 담당하여 실행기를 중복 생성하지 않는다.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol

from .handoff_navigation import NavigationBinding, NavigationStep, AlignmentStep, Check


class MotionAction(Protocol):
    def execute(self, reference: Any, check: Check) -> Any: ...


@dataclass(frozen=True)
class PathMotion:
    """한 설정 프로파일과 경로 실행 기능의 조합. 목표는 요청마다 계산한다."""
    stage: str
    binding: NavigationBinding
    plan: Callable
    run: Callable

    def execute(self, reference: Any, check: Check) -> Any:
        check()
        step = self.plan(self.stage, reference, check)
        if not isinstance(step, NavigationStep):
            raise TypeError('경로 실행 계획 필요')
        return self.run(self.stage, self.binding, step, check)


@dataclass(frozen=True)
class SpinMotion:
    """미리 연결한 Spin 실행 기능. 속도 파라미터를 변경하지 않는다."""
    stage: str
    plan: Callable
    run: Callable

    def execute(self, reference: Any, check: Check) -> Any:
        check()
        step = self.plan(self.stage, reference, check)
        if not isinstance(step, AlignmentStep):
            raise TypeError('방향 조정 계획 필요')
        return self.run(step, check)


@dataclass(frozen=True)
class SequenceMotion:
    """각 동작 정지 확인 후 다음으로 진행한다. 실패·취소는 상위로 전달한다."""
    actions: tuple

    def execute(self, reference: Any, check: Check) -> Any:
        results = []
        for action in self.actions:
            check()
            results.append(action.execute(reference, check))
        return {'components': results}


class ComponentSteps:
    """팀원이 같은 execute 계약을 구현하여 동작 조합을 교체하는 경계.

공유 실행기의 stop을 주입한다. 실패한 동작의 정리 책임을 잃지 않도록
이 객체 자체가 임의로 활성 동작이나 소유권을 초기화하지 않는다.
"""
    def __init__(self, *, capture: Callable, actions: Mapping[str, MotionAction],
                 stop: Check) -> None:
        required = {'departure', 'wall', 'retreat', 'align', 'return'}
        if set(actions) != required:
            raise ValueError('차체 동작 5단계 조합 필요')
        if any(not callable(getattr(action, 'execute', None)) for action in actions.values()):
            raise TypeError('동작 객체는 execute 계약이 필요합니다.')
        self.actions = MappingProxyType(dict(actions))
        self._capture, self._stop = capture, stop

    def capture(self, check: Check) -> Any:
        check()
        return self._capture(check)

    def execute(self, stage: str, reference: Any, check: Check) -> Any:
        check()
        if stage not in self.actions:
            raise ValueError('알 수 없는 차체 단계')
        return self.actions[stage].execute(reference, check)

    def stop(self) -> None:
        self._stop()
