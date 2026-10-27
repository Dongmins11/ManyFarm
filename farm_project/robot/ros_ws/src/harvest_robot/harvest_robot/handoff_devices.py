"""기존 TransferMission 장치 계약과 조합형 차체 동작을 연결한다."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any, Callable
from .transfer_devices import DeviceResult, DeviceNotStarted


class ComponentTransferDevices:
    """비차체 장치는 기존 어댑터를 사용하고 차체만 enter/restore로 교체한다.

소유권은 TransferCommunication의 transfer 예약을 그대로 사용한다.
restore는 기존 미션이 TRANSPORT_CLEAR를 확인한 뒤에만 요청한다.
"""
    def __init__(self, devices: Any, build_body: Callable, ready: Callable,
                 timeout_s: float, stop_timeout_s: float, *, clock_factory=None) -> None:
        self.clock_factory = clock_factory
        self.devices = devices
        self._build, self._ready = build_body, ready
        self._timeout, self._stop_timeout = timeout_s, stop_timeout_s
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='handoff_devices')
        self._cancel = threading.Event()
        self._lock = threading.RLock()
        self._ticket = None
        self._body = None
        self._entered = False
        self._closed = False

    def ready(self) -> bool:
        return (not self._closed and not self._cancel.is_set()
                and (self._ticket is None or self._ticket.done())
                and self.devices.ready() and self._ready())

    def start(self, operation: str) -> Any:
        with self._lock:
            if self._closed:
                raise RuntimeError('종료된 인계 장치')
            if operation == 'stop':
                self._cancel.set()
                return self._pool.submit(self._stop)
            if self._cancel.is_set() or (self._ticket and not self._ticket.done()):
                raise RuntimeError('기존 인계 작업 종료/복구 확인 필요')
            if operation not in ('prepare_arm', 'rotate_to_transfer', 'discharge', 'restore'):
                raise ValueError('지원하지 않는 인계 동작')
            self._ticket = self._pool.submit(self._run, operation)
            return self._ticket

    def poll(self, ticket: Any) -> DeviceResult:
        if not ticket.done():
            return DeviceResult(False)
        try:
            ticket.result()
            return DeviceResult(True, True)
        except DeviceNotStarted as error:
            return DeviceResult(True, False, str(error), not_started=True)
        except Exception as error:
            return DeviceResult(True, False, str(error))

    def _await(self, source: Any, ticket: Any, *, stopping: bool = False) -> None:
        clock = (self.clock_factory() if self.clock_factory is not None and source is self._body and not stopping else time.monotonic)
        deadline = clock() + (self._stop_timeout if stopping else self._timeout)
        while True:
            if not stopping and self._cancel.is_set():
                raise RuntimeError('차체 인계 중단')
            if clock() >= deadline:
                raise TimeoutError('인계 동작 완료 시간 초과')
            result = source.poll(ticket)
            if result.completed:
                if not result.ok:
                    raise RuntimeError(result.detail)
                return
            time.sleep(.01)

    def _run(self, operation: str) -> None:
        if self._cancel.is_set():
            raise RuntimeError('차체 인계 중단')
        if operation == 'prepare_arm':
            if self._body is not None:
                raise RuntimeError('이전 차체 작업 정리 필요')
            self._await(self.devices, self.devices.start('prepare_arm'))
            self._body = self._build()
        elif operation == 'rotate_to_transfer':
            if self._body is None or self._entered:
                raise RuntimeError('차체 준비 상태 불일치')
            self._await(self._body, self._body.start('enter'))
            self._entered = True
        elif operation == 'discharge':
            if not self._entered:
                raise RuntimeError('진입 완료 전 배출 금지')
            self._await(self.devices, self.devices.start('discharge'))
        elif operation == 'restore':
            if not self._entered or self._body is None:
                raise RuntimeError('복귀 기준 없음')
            self._await(self.devices, self.devices.start('restore_devices'))
            self._await(self._body, self._body.start('restore'))
            self._body.close()
            self._body = None
            self._entered = False

    def _stop(self) -> None:
        errors = []
        pending = []
        # 양쪽에 먼저 중단 요청한 후 결과를 기다린다.
        for source in (self._body, self.devices):
            if source is None:
                continue
            try:
                pending.append((source, source.start('stop')))
            except Exception as error:
                errors.append(str(error))
        for source, ticket in pending:
            try:
                self._await(source, ticket, stopping=True)
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))

    def close(self, node: Any) -> None:
        self._cancel.set()
        self._pool.shutdown(wait=True)
        self._closed = True
        if self._body is not None:
            self._body.close()
        self.devices.close(node)
