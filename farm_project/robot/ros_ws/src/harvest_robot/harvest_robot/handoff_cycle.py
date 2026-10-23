"""기존 작업 소유권 안에서 그래프 이동과 새 차체 클래스를 순서대로 호출한다.

run은 기존 I/O 작업 스레드에서 호출한다. Node/State/액션 서버를 생성하지 않는다.
좌표와 최종 방향은 호출자가 해당 환경 그래프에서 해석해 전달한다.
"""
from concurrent.futures import TimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from .handoff_motion import HarvestHandoffMotion


@dataclass(frozen=True)
class GraphGoal:
    xy: tuple[float, float]
    yaw: float


class HandoffCycle:
    """Node의 동일 ActionHandoff를 주입한다. 정지 실패 시 예약을 유지한다.

build_graph(check)는 기존 Navigator를, build_body(check)는 새 차체 클래스를
구성한다. stop_graph는 자신의 Goal 취소와 MotionMonitor 정지 확인까지 수행한다.
"""

    def __init__(self, *, handoff: Any,
                 build_graph: Callable[[Callable[[], None]], Any],
                 build_body: Callable[[Callable[[], None]], HarvestHandoffMotion],
                 stop_graph: Callable[[Any], None]) -> None:
        self._handoff = handoff
        self._build_graph = build_graph
        self._build_body = build_body
        self._stop_graph = stop_graph
        self._retained: tuple[str, Any, Any, bool] | None = None

    def run(self, task_id: str, entry: GraphGoal, exit: GraphGoal,
            check: Callable[[], None]) -> dict:
        """12번/14번 등 식별자를 하드코딩하지 않는다. 기존 그래프 경로를 사용한다."""
        if not task_id:
            raise ValueError('작업 ID 필요')
        kind = 'handoff_cycle'
        if not self._handoff.reserve(kind, task_id, preempt=False, interruptible=False):
            raise RuntimeError('다른 작업 실행 중')
        graph = body = None
        graph_active = False
        release = True
        completed = []
        try:
            token = self._handoff.acquire(kind, task_id, check)

            def checked() -> None:
                check()
                if token.interrupted.is_set():
                    raise RuntimeError('연속 동작 중단')

            checked()
            graph = self._build_graph(checked)
            body = self._build_body(checked)
            graph.preflight_navigation()
            checked()
            graph_active = True
            graph.navigate(entry.xy, entry.yaw)
            graph_active = False
            completed.append('entry')
            for operation in ('enter', 'restore'):
                checked()
                ticket = body.start(operation)
                while True:
                    checked()
                    try:
                        result = ticket.result(timeout=.05)
                        break
                    except TimeoutError:
                        # 작업 자체에서 발생한 TimeoutError도 구별해 전달한다.
                        if ticket.done():
                            result = ticket.result()
                            break
                completed.extend(result.stages)
            checked()
            graph_active = True
            graph.navigate(exit.xy, exit.yaw)
            graph_active = False
            checked()
            completed.append('exit')
            body.close()
            body = None
            return {'completed': tuple(completed)}
        except BaseException as original:
            errors = self._cleanup(graph, body, graph_active)
            if errors:
                release = False
                self._retained = (task_id, graph, body, graph_active)
                raise RuntimeError(f'{original}; 정지 미확인: {errors}') from original
            raise
        finally:
            if release:
                self._handoff.release(kind, task_id)

    def _cleanup(self, graph: Any, body: Any, graph_active: bool) -> list[str]:
        errors = []
        if body is not None:
            try:
                body.start('stop').result()
            except BaseException as error:
                errors.append(str(error))
        if graph is not None and graph_active:
            try:
                self._stop_graph(graph)
            except BaseException as error:
                errors.append(str(error))
        if body is not None and not errors:
            body.close()
        return errors

    def retry_stop(self) -> None:
        """실패한 정지 확인만 재시도한다. 이동 단계는 재실행하지 않는다."""
        if self._retained is None:
            return
        task_id, graph, body, active = self._retained
        errors = self._cleanup(graph, body, active)
        if errors:
            raise RuntimeError('정지 미확인: ' + '; '.join(errors))
        self._handoff.release('handoff_cycle', task_id)
        self._retained = None
