"""수확 차체 순서만 관리한다. 서버·ROS 노드·설정 파일을 생성하지 않는다.

연결부는 기존 Navigator/SpinClient와 안전 감시를 구성해 MotionSteps로 제공한다.
각 단계는 정지 확인까지 끝낸 뒤 반환하고, 대기 중 check를 호출해야 한다.
운영 출력 경로가 연결되기 전에는 이 모듈만으로 실물 실행할 수 없다.
"""
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event, RLock
from typing import Any, Callable, Protocol

from .transfer_devices import DeviceResult


class MotionSteps(Protocol):
    """기존 실행 기능을 연결하는 경계. 내부에서 새 임시 서버를 열지 않는다."""

    def capture(self, check: Callable[[], None]) -> Any: ...
    def execute(self, stage: str, reference: Any,
                check: Callable[[], None]) -> Any: ...
    def stop(self) -> None:
        """자신의 Goal 취소 및 실제 정지 확인. 실패하면 예외를 반환한다."""
        ...


@dataclass(frozen=True)
class MotionResult:
    operation: str
    stages: tuple[str, ...]
    measurements: tuple[Any, ...]


class HarvestHandoffMotion:
    """start는 즉시 Future를 반환한다. 완료 콜백의 상태 전이는 호출자가 맡는다.

로봇 전체 실행 소유권은 기존 ActionHandoff에서 확보한 후 호출해야 한다.
이 객체의 잠금은 자기 자신에 대한 중복 요청만 막는다.
"""

    def __init__(self, steps: MotionSteps) -> None:
        self._steps = steps
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='handoff_motion')
        self._lock = RLock()
        self._cancel = Event()
        self._ticket: Future | None = None
        self._operation = ''
        self._phase = 'IDLE'
        self._reference = None
        self._closed = False

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    def start(self, operation: str) -> Future:
        """enter/restore/stop을 요청한다. 실패 후 자동 재실행하지 않는다."""
        with self._lock:
            if self._closed:
                raise RuntimeError('종료된 차체 실행기')
            if operation not in ('enter', 'restore', 'stop'):
                raise ValueError('지원하지 않는 차체 동작: ' + operation)
            active = self._ticket is not None and not self._ticket.done()
            if operation == 'stop':
                self._cancel.set()
                if active and self._operation == 'stop':
                    return self._ticket
                self._phase = 'STOPPING'
                self._operation = operation
                self._ticket = self._pool.submit(self._stop)
                return self._ticket
            if active:
                raise RuntimeError('차체 동작 실행 중')
            expected = 'IDLE' if operation == 'enter' else 'ENTERED'
            if self._phase != expected or self._cancel.is_set():
                raise RuntimeError('현재 상태에서 요청할 수 없음: ' + self._phase)
            self._operation = operation
            self._phase = 'ENTERING' if operation == 'enter' else 'RESTORING'
            self._ticket = self._pool.submit(self._run, operation)
            return self._ticket

    def _check(self) -> None:
        if self._cancel.is_set():
            raise RuntimeError('차체 동작 중단 요청')

    def _run(self, operation: str) -> MotionResult:
        stages = ('departure', 'wall') if operation == 'enter' else ('retreat', 'align', 'return')
        values = []
        try:
            self._check()
            if operation == 'enter':
                self._reference = self._steps.capture(self._check)
            for stage in stages:
                self._check()
                values.append(self._steps.execute(stage, self._reference, self._check))
            with self._lock:
                self._check()
                self._phase = 'ENTERED' if operation == 'enter' else 'IDLE'
                if operation == 'restore':
                    self._reference = None
            return MotionResult(operation, stages, tuple(values))
        except BaseException as error:
            try:
                self._steps.stop()
            except BaseException as stop_error:
                with self._lock:
                    self._phase = 'STOP_UNCONFIRMED'
                raise RuntimeError(f'{error}; 정지 미확인: {stop_error}') from error
            with self._lock:
                self._phase = 'INTERRUPTED'
            raise

    def _stop(self) -> MotionResult:
        try:
            self._steps.stop()
        except BaseException:
            with self._lock:
                self._phase = 'STOP_UNCONFIRMED'
            raise
        with self._lock:
            self._phase = 'INTERRUPTED'
        return MotionResult('stop', (), ())

    def poll(self, ticket: Future) -> DeviceResult:
        """기존 장치 결과 형식을 재사용한다. 작업 접수와 완료를 구분한다."""
        if not ticket.done():
            return DeviceResult(False)
        try:
            ticket.result()
            return DeviceResult(True, True)
        except Exception as error:
            return DeviceResult(True, False, str(error))

    def close(self) -> None:
        """실행 중이면 중단 요청 후 작업 종료를 기다린다. ROS 콜백은 계속 돌아야 한다."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._cancel.set()
        self._pool.shutdown(wait=True)
        if self.phase == 'STOP_UNCONFIRMED':
            raise RuntimeError('종료 시 차체 정지 미확인')


def configured_motion(config: dict, build_steps: Callable[[dict], MotionSteps]) -> HarvestHandoffMotion | None:
    """새 선택값이 없으면 아무 의존성도 생성하지 않는다. 기존 설정 기본값 보존."""
    selection = config.get('handoff_motion')
    if selection is None:
        return None
    if not isinstance(selection, dict):
        raise ValueError('handoff_motion은 객체여야 합니다.')
    if selection.get('implementation') != 'arc_wall':
        raise ValueError('알 수 없는 handoff_motion 구현')
    return HarvestHandoffMotion(build_steps(selection))
