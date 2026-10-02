"""상태 전환의 단일 소유자. ROS 타이머가 이벤트를 처리하고 I/O는 별도 수행합니다."""
from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TypeVar, Any
from _thread import LockType

from farm_interfaces.action import ScoutArea
from rclpy.action.server import ServerGoalHandle

from .runtime import MissionCanceled
from .scout_mission import ScoutMission
from .states.idle_state import IdleState
from .states.mission_state import MissionState

T = TypeVar('T')


class ScoutStateController:
    def __init__(self, mission: ScoutMission) -> None:
        self._mission: ScoutMission = mission
        self._events: queue.Queue[Callable[[], None]] = queue.Queue()
        # 한 작업의 이동·영상 RPC·정리를 직렬화합니다. State enter는 기다리지 않습니다.
        self._io: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='scout_io')
        self._current_state: MissionState = IdleState(mission, self)
        self._generation: int = 0  # 이전 State/미션의 늦은 응답을 걸러냅니다.
        self._result: Future[ScoutArea.Result] | None = None
        self._operation: Future[Any] | None = None
        self._stopping: bool = False
        self._stop_requested: threading.Event = threading.Event()
        self._update_lock: LockType = threading.Lock()
        self._current_state.enter()

    @property
    def state_name(self) -> str:
        return self._current_state.name

    @property
    def finishing(self) -> bool:
        return self._stopping and self._result is not None

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested.is_set()

    def start(self, goal: ServerGoalHandle) -> Future[ScoutArea.Result]:
        """통신 콜백은 시작 이벤트만 등록합니다. 상태 변경은 update에서만 합니다."""
        result: Future[ScoutArea.Result] = Future()
        self._events.put(lambda: self._begin(goal, result))
        return result

    def _begin(self, goal: ServerGoalHandle, result: Future[ScoutArea.Result]) -> None:
        if self._result is not None:
            result.set_exception(RuntimeError('이미 실행 중인 미션이 있습니다.'))
            return
        self._result = result
        self._stopping = False
        self._stop_requested.clear()
        try:
            self._mission.begin(goal)
        except Exception as error:
            self._result = None
            result.set_exception(error)
            return
        if goal.is_cancel_requested or self._mission.node._shutdown_requested:
            self._stop(MissionCanceled('ScoutArea canceled before start'))
            return
        from .states.navigation_move_state import NavigationMoveState
        self._change_state(NavigationMoveState(self._mission, self, 'section_start'))

    def update(self) -> None:
        """AnyState 조건을 먼저 검사한 뒤, 정상 완료 이벤트를 처리합니다."""
        # 콜백 그룹 설정과 별개로 중첩 update도 막습니다.
        if not self._update_lock.acquire(blocking=False):
            return
        try:
            for _ in range(32):
                if self._result is not None and not self._stopping:
                    goal = self._mission.context.goal
                    if goal.is_cancel_requested or self._mission.node._shutdown_requested:
                        self._stop(MissionCanceled('ScoutArea canceled'))
                try:
                    event = self._events.get_nowait()
                except queue.Empty:
                    break
                try:
                    event()
                except Exception as error:
                    self._stop(error)
        finally:
            self._update_lock.release()

    def request_transition(self, source: MissionState, target: MissionState) -> None:
        """State는 요청만 합니다. 실제 Exit/Enter는 Controller가 실행합니다."""
        generation = self._generation

        def transition() -> None:
            if self._valid(source, generation):
                self._change_state(target)

        self._events.put(transition)

    def _change_state(self, state: MissionState) -> None:
        if self._operation is not None:
            raise RuntimeError('동작이 끝나기 전에 정상 상태 전환을 요청했습니다.')
        self._current_state.exit()
        self._generation += 1
        self._current_state = state
        self._mission.node.get_logger().info(f'예찰 상태: {state.name}')
        self._current_state.enter()

    def _valid(self, state: MissionState, generation: int) -> bool:
        return (
            not self._stopping
            and self._result is not None
            and generation == self._generation
            and state is self._current_state
            and state.active
        )

    def run_async(self, state: MissionState, action: Callable[[], T], completed: Callable[[T], None]) -> None:
        """실제 I/O·계산을 요청하고 반환합니다. 완료 함수는 update에서만 호출합니다."""
        if self._stopping or state is not self._current_state or not state.active:
            return
        if self._operation is not None:
            raise RuntimeError('한 State에서 동시에 두 I/O 작업을 요청했습니다.')
        generation = self._generation
        future = self._io.submit(action)
        self._operation = future

        def deliver() -> None:
            if not self._valid(state, generation):
                return
            self._operation = None
            # 오류도 같은 단일 경로로 전달되어 update의 AnyState 처리로 들어갑니다.
            completed(future.result())

        future.add_done_callback(lambda _: self._events.put(deliver))

    def complete(self, state: MissionState) -> None:
        """최종 State가 작업 완료를 요청합니다. 자원 정리 후 결과를 전달합니다."""
        if not self._valid(state, self._generation):
            return
        self._finish('SUCCESS', None)

    def _stop(self, error: Exception) -> None:
        """AnyState 공통 경로: 정상 진행 차단 → 동작 중단 확인 → Exit → 결과."""
        if self._result is None or self._stopping:
            return
        code = 'CANCELED' if isinstance(error, MissionCanceled) else 'FAILED'
        self._mission.node.get_logger().error(str(error))
        self._finish(code, error)

    def _finish(self, code: str, error: Exception | None) -> None:
        self._stopping = True
        self._stop_requested.set()
        self._generation += 1  # 이미 큐에 들어온 정상 완료 알림도 무효화합니다.
        try:
            if code != 'SUCCESS':
                self._current_state.on_stop_requested()
        except Exception as stop_error:
            code, error = 'FAILED', stop_error
        # 같은 I/O 큐에 넣어 진행 중 RPC/이동 코드와 정리 작업이 경쟁하지 않게 합니다.
        cleanup = self._io.submit(self._cleanup, code, error)
        cleanup.add_done_callback(lambda _: self._events.put(lambda: self._on_cleaned(cleanup)))

    def _cleanup(self, code: str, error: Exception | None) -> ScoutArea.Result:
        started = time.monotonic()
        node = self._mission.node
        if code != 'SUCCESS':
            try:
                node._navigator.cancel_nav()
            except Exception as cancel_error:
                node._motion_uncertain = True
                node.get_logger().error(f'Nav2 종료 확인 실패: {cancel_error}')
                error = RuntimeError(f'{error}; Nav2 종료 확인 실패: {cancel_error}')
        try:
            self._mission.close_observer(reusable=code == 'SUCCESS')
        except Exception as cleanup_error:
            node._motion_uncertain = True  # 자원 종료가 불확실하면 새 작업도 차단합니다.
            code = 'FAILED'
            error = RuntimeError(f'{error or ""}; 영상 워커 종료 실패: {cleanup_error}')
        self._mission.context.report['worker_cleanup_wall_s'] = time.monotonic() - started
        return self._mission.finish(code, error)

    def _on_cleaned(self, cleanup: Future[ScoutArea.Result]) -> None:
        result_future = self._result
        assert result_future is not None
        self._operation = None
        error: Exception | None = None
        result: ScoutArea.Result | None = None
        try:
            result = cleanup.result()
            self._current_state.exit()  # 장치 정리 뒤 상태 수명을 종료합니다.
        except Exception as cleanup_error:
            error = cleanup_error
            self._mission.node._motion_uncertain = True
        finally:
            self._current_state = IdleState(self._mission, self)
            self._current_state.enter()
            self._result = None
        if error is not None:
            result_future.set_exception(error)
        else:
            assert result is not None
            result_future.set_result(result)
        # 중단 플래그는 다음 _begin에서 해제합니다. 이전 작업 응답이 재개되지 않습니다.

    def close(self) -> None:
        """작업 결과 반환 후 Node 종료 단계에서 호출합니다."""
        self._io.shutdown(wait=True, cancel_futures=True)
