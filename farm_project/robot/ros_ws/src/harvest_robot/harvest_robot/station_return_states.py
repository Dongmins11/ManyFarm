"""복귀 준비·후진·정리 상태. I/O 완료는 큐를 거쳐 Controller만 전환한다."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue
from typing import Any, Callable


class ReturnState:
    """enter는 작업을 예약하고 반환하며 exit는 별도 출력을 내지 않는다."""

    operation = ''

    def enter(self, controller: ReturnController) -> None:
        controller.run_async(self, getattr(controller.mission, self.operation))

    def exit(self, controller: ReturnController) -> None:
        pass

    def completed(self, controller: ReturnController, future: Future) -> None:
        raise NotImplementedError


class PrepareReturnState(ReturnState):
    operation = 'prepare'

    def completed(self, controller: ReturnController, future: Future) -> None:
        future.result()
        controller.transition(ReverseReturnState())


class ReverseReturnState(ReturnState):
    operation = 'navigate'

    def completed(self, controller: ReturnController, future: Future) -> None:
        future.result()
        controller.transition(DockReturnState() if getattr(controller.mission, "docking_enabled", False)
                              else CleanupReturnState())


class DockReturnState(ReturnState):
    """관측·제어 작업은 예약하고 완료 콜백에서만 정리로 전환한다."""

    operation = 'dock'

    def completed(self, controller: ReturnController, future: Future) -> None:
        future.result()
        controller.transition(CleanupReturnState())


class CleanupReturnState(ReturnState):
    operation = 'cleanup'

    def completed(self, controller: ReturnController, future: Future) -> None:
        try:
            future.result()
        except Exception as error:
            controller.cleanup_error = error
        controller.transition(None)


class ReturnController:
    """한 Action 안에서 상태 전환을 직렬화한다. 새 Goal마다 새 인스턴스를 사용한다."""

    def __init__(self, mission: Any) -> None:
        self.mission = mission
        self.error: Exception | None = None
        self.cleanup_error: Exception | None = None
        self._state: ReturnState | None = None
        self._epoch = 0
        self._events: Queue = Queue()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='harvest_return')

    def transition(self, state: ReturnState | None) -> None:
        if self._state is not None:
            self._state.exit(self)
        self._epoch += 1
        self._state = state
        if state is not None:
            state.enter(self)

    def run_async(self, state: ReturnState, operation: Callable[[], None]) -> None:
        epoch = self._epoch
        future = self._pool.submit(operation)
        future.add_done_callback(lambda done: self._events.put((epoch, state, done)))

    def run(self) -> None:
        """Action 실행 스레드에서 완료를 기다린다. ROS 콜백은 기존 executor가 처리한다."""
        try:
            self.transition(PrepareReturnState())
            while self._state is not None:
                epoch, state, future = self._events.get()
                if epoch != self._epoch or state is not self._state:
                    continue
                try:
                    state.completed(self, future)
                except Exception as error:
                    self.error = error
                    self.transition(CleanupReturnState())
            if self.error is not None:
                raise self.error
        finally:
            self._pool.shutdown(wait=True)
