"""State enter는 작업을 예약하고 반환합니다. 완료 콜백에서 종결 상태로 전환합니다."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event


class NavigationState:
    def enter(self, controller) -> None:
        future = controller.pool.submit(controller.mission.run)
        future.add_done_callback(controller.completed)

    def exit(self, controller) -> None:
        pass


class TerminalState:
    def enter(self, controller) -> None:
        controller.done.set()

    def exit(self, controller) -> None:
        pass


class HarvestStateController:
    def __init__(self, mission) -> None:
        self.mission = mission
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='harvest_navigation')
        self.done = Event()
        self.state = None
        self.outcome = None
        self.error = None

    def transition(self, state) -> None:
        if self.state is not None:
            self.state.exit(self)
        self.state = state
        self.state.enter(self)

    def start(self) -> None:
        self.transition(NavigationState())

    def completed(self, future) -> None:
        try:
            self.outcome = future.result()
        except Exception as error:
            self.error = error
        self.transition(TerminalState())

    def close(self) -> None:
        self.pool.shutdown(wait=True)
