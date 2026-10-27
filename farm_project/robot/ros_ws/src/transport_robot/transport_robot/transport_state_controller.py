"""단일 전환 경로·I/O 큐·세대 확인·취소 후 정지 확인을 관리한다."""
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue, Empty
from threading import Event
from typing import Callable, Any
from .mission_types import Request, Outcome, MissionCanceled
from .states.navigation_move_state import NavigationMoveState
from .states.docking_state import DockingState
from .transfer_session import TransferSession
from .unload_session import UnloadSession
from .device_port import UnavailableDevice


class TransportStateController:
    def __init__(self, navigator: Any, mission: Any, docking: Any, device: Any = None) -> None:
        self.navigator, self.mission, self.docking = navigator, mission, docking
        self.device = device or UnavailableDevice()
        self.transfer = TransferSession()
        self.unload = UnloadSession()
        self.docked_request = None
        self.parked_request = None
        self.parking_profiles = set()
        self.unload_workflows = {}
        self.pickup_workflow = {}
        self.station_return_mode = 'marker_docking'
        self.loaded_count = None
        self._pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='transport_io')
        self._events = Queue()
        self._cancel = Event()
        self._epoch = 0
        self._stopping = False
        self.blocked = mission.recovery_required
        self.last_outcome = None
        self.request = None
        self.state = None
        self.result = None
        self.feedback = lambda phase: None

    @property
    def busy(self) -> bool:
        return self.result is not None and not self.result.done()

    def check(self) -> None:
        if self._cancel.is_set():
            raise MissionCanceled('작업 취소/종료 요청')

    def start(self, request: Request, feedback: Callable[[str],None]) -> Future:
        if request.kind not in ('route', 'return', 'pickup', 'unload'):
            raise ValueError('지원하지 않는 운송 작업 종류')
        if self.busy or self.blocked:
            raise RuntimeError('작업 중이거나 정지/복구 확인이 필요합니다.')
        navigation_return = request.kind == 'return' and self.station_return_mode == 'navigation_only'
        if request.kind != 'route' and not navigation_return and not self.docking.available():
            raise ValueError('ReturnToStation은 도킹 연결 후 사용 가능합니다.')
        if request.kind in ('pickup','unload') and not (request.kind == 'unload' and request.dock_only_trial) and not self.device.available():
            raise ValueError('기구 브릿지 미연결')
        if request.dock_only_trial and request.kind != 'unload':
            raise ValueError('도킹 시험은 unload 작업에만 허용')
        if self.docked_request is not None and self.docked_request.dock_only_trial:
            raise ValueError('도킹 단독 시험 후 이격 검증/복구 필요')
        if request.kind == 'pickup' and not self.pickup_workflow.get('enabled') and not getattr(self.device, 'supports', lambda op: True)('CONFIRM_RECEIPT'):
            raise ValueError('수령/수량 검증 장치 미연결')
        self.mission.begin(request)
        self.parked_request = None
        if request.kind == 'pickup': self.transfer.begin(request)
        if request.kind == 'unload': self.unload.begin(request)
        self.request, self.feedback = request, feedback
        self._cancel.clear()
        self._stopping = False
        self.result = Future()
        if self.docked_request is not None:
            from .states.transfer_states import ClearingState
            self.transition(ClearingState(self,departure=True))
        else:
            self.transition(NavigationMoveState(self))
        return self.result

    def transition(self, state: Any) -> None:
        if self.state is not None:
            self.state.exit()
        self._epoch += 1
        self.state = state
        try:
            state.enter()
        except Exception as exc:
            self._stop(Outcome('FAILED','INTERNAL_ERROR',str(exc)))

    def run_async(self, state: Any, operation: Callable, completed: Callable) -> None:
        epoch = self._epoch
        future = self._pool.submit(operation)
        future.add_done_callback(lambda done: self._events.put(('io',epoch,state,done,completed)))

    def cancel(self) -> None:
        self._cancel.set()

    def update(self) -> None:
        if self.busy and self._cancel.is_set() and not self._stopping:
            self._stop(Outcome('CANCELED'))
        while True:
            try:
                event = self._events.get_nowait()
            except Empty:
                break
            if event[0] == 'cleanup':
                _, future, outcome = event
                try:
                    future.result()
                    if (self.state is not None and self.state.name == 'DOCKING'
                            and getattr(self.docking,'pre_entry_stopped',False)):
                        self.mission.set_contact(False)
                except Exception as exc:
                    self.blocked = True
                    outcome = Outcome('FAILED','INTERNAL_ERROR','정지 확인 실패: '+str(exc))
                self.finish(outcome)
            else:
                _, epoch, state, future, callback = event
                if self._stopping or epoch != self._epoch or state is not self.state:
                    continue
                try:
                    self.check()
                    callback(future.result())
                except MissionCanceled:
                    self._stop(Outcome('CANCELED'))
                except Exception as exc:
                    code = {'DOCKING': 'DOCK_FAILED', 'UNLOADING': 'UNLOAD_FAILED', 'CLEARING': 'CLEARANCE_FAILED'}.get(self.state.name, 'NAVIGATION_FAILED')
                    if self.state.__class__.__name__ == 'WaitUnloadState' and isinstance(exc, TimeoutError):
                        code = 'UNLOAD_READY_TIMEOUT'
                    detail = str(exc)
                    if self.state.name == 'CLEARING' and self.request.kind == 'unload':
                        detail = '하역 완료 후 도킹해제 실패: ' + detail
                    self._stop(Outcome('FAILED',code,detail))

    def arrived(self) -> None:
        if self.request.kind == 'pickup':
            from .states.transfer_states import TaggingState
            self.transition(TaggingState(self))
        elif self.request.kind == 'unload':
            self.unload.stage('DOCKING')
            self.transition(DockingState(self))
        elif self.request.kind == 'return':
            if self.station_return_mode == 'navigation_only':
                # Navigator가 실제 도착 오차와 정지를 확인한 이후에만 호출된다.
                self.mission.record_stage(self.request, 'STATION_PARKED', 'marker_stage=SKIPPED_SIM_POLICY')
                self.feedback('ARRIVED')
                self.finish(Outcome('SUCCESS', arrived=True, docked=True))
                return
            if self.request.kind == 'return': self.feedback('APPROACHING')
            self.transition(DockingState(self))
        else:
            self.feedback('ARRIVED')
            self.finish(Outcome('SUCCESS',arrived=True))

    def _stop(self, outcome: Outcome) -> None:
        if self._stopping:
            return
        self._stopping = True
        self._cancel.set()
        self._epoch += 1
        # 같은 I/O 큐에서 진행 요청이 반환한 뒤 장치를 정리한다.
        def cleanup() -> None:
            errors=[]
            for stop in (self.navigator.cancel_nav,self.docking.stop,self.device.stop):
                try:stop()
                except Exception as exc:errors.append(str(exc))
            if errors:raise RuntimeError('; '.join(errors))
        future = self._pool.submit(cleanup)
        future.add_done_callback(lambda done: self._events.put(('cleanup',done,outcome)))

    def finish(self, outcome: Outcome) -> None:
        if self.state is not None:
            self.state.exit()
        self._epoch += 1
        self.state = None
        try:
            self.mission.finish(self.request,outcome)
        except Exception as exc:
            self.blocked = True
            outcome = Outcome('FAILED','INTERNAL_ERROR','작업 기록 저장 실패: '+str(exc))
        self.transfer.close()
        self.unload.close()
        if outcome.result_code != 'SUCCESS' and self.mission._contact.exists():
            self.blocked = True
        self.last_outcome = outcome
        self.result.set_result(outcome)

    def close(self) -> None:
        self._pool.shutdown(wait=True)
