"""Existing OpenCR Trigger services behind the transport device port.

UNLOAD and optional lid services: timed completion is not a verified fruit count.
No retries. Cancellation sends STOP and drains the original service response.
"""
from dataclasses import dataclass
from threading import Lock
import math
import time
from std_srvs.srv import Trigger


@dataclass(frozen=True)
class UnloadCompletion:
    success: bool
    message: str


class TriggerDevice:
    def __init__(self, node, group, config):
        self.node = node
        self.timeout = float(config.get('unload_timeout_s', 45.0))
        self.stop_timeout = float(config.get('stop_timeout_s', 3.0))
        self.drain_timeout = float(config.get('drain_timeout_s', 45.0))
        if not all(math.isfinite(v) and v > 0 for v in (self.timeout, self.stop_timeout, self.drain_timeout)):
            raise ValueError('Device timeouts must be finite and positive')
        self.client = node.create_client(Trigger, config.get('unload_service', 'device/unload'), callback_group=group)
        self.clients = {'UNLOAD': self.client}
        if config.get('pickup_lid_enabled', False):
            for operation, key, default in [('LID_OPEN', 'lid_open_service', 'device/lid_open'), ('LID_CLOSE', 'lid_close_service', 'device/lid_close')]:
                self.clients[operation] = node.create_client(Trigger, config.get(key, default), callback_group=group)
        self.stop_client = node.create_client(Trigger, config.get('stop_service', 'device/stop'), callback_group=group)
        self.pending = None
        self.uncertain = False
        self._lock = Lock()
        self._stop_sent = False
        self._stop_error = None

    def supports(self, operation):
        return operation in self.clients

    def available(self):
        return (not self.uncertain and self.pending is None and
                self.client.service_is_ready() and self.stop_client.service_is_ready())

    def operation_ready(self, operation):
        return self.available() and operation in self.clients and self.clients[operation].service_is_ready()

    @staticmethod
    def _wait(future, timeout):
        deadline = time.monotonic() + timeout
        while not future.done():
            if time.monotonic() >= deadline:
                raise TimeoutError('Device service response timeout')
            time.sleep(.02)
        return future.result()

    def run(self, request, operation, check):
        if not self.supports(operation):
            raise RuntimeError('Trigger backend supports UNLOAD only; receipt/count integration pending')
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('Device operation already running')
        try:
            check()
            if not self.operation_ready(operation):
                raise RuntimeError('Unload/stop services unavailable or previous operation unresolved')
            self._stop_sent = False
            self._stop_error = None
            self.pending = self.clients[operation].call_async(Trigger.Request())
            self.node.get_logger().info(f'{operation} requested once: task_id={request.task_id}')
            try:
                deadline = time.monotonic() + self.timeout
                while not self.pending.done():
                    check()
                    if time.monotonic() >= deadline:
                        raise TimeoutError(operation + ' response timeout; not retried')
                    time.sleep(.02)
                check()  # cancellation wins even when DONE arrived concurrently
                response = self.pending.result()
                if not response.success:
                    raise RuntimeError(operation + ' failed: ' + response.message)
                self.pending = None
                return UnloadCompletion(True, response.message)
            except Exception as exc:
                self.uncertain = True
                try:
                    self._stop_and_drain()
                except Exception as stop_exc:
                    raise RuntimeError(f'{exc}; stop/response unresolved: {stop_exc}') from exc
                raise
        finally:
            self._lock.release()

    def _stop_and_drain(self):
        if self._stop_sent:
            if self._stop_error:
                raise RuntimeError(self._stop_error)
            return
        self._stop_sent = True
        errors = []
        try:
            if not self.stop_client.service_is_ready():
                raise RuntimeError('Device stop service unavailable')
            response = self._wait(self.stop_client.call_async(Trigger.Request()), self.stop_timeout)
            if not response.success:
                raise RuntimeError('Device stop rejected: ' + response.message)
        except Exception as exc:
            errors.append(str(exc))
        # STOP ACK alone is not the terminal response of the unload operation.
        if self.pending is not None:
            try:
                self._wait(self.pending, self.drain_timeout)
                self.pending = None
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            self._stop_error = '; '.join(errors)
            raise RuntimeError(self._stop_error)

    def stop(self):
        # Controller invokes cleanup after the I/O worker returns.
        if self.pending is not None or self._stop_error:
            self._stop_and_drain()

    def recovery_ready(self):
        return not self._lock.locked() and (self.pending is None or self.pending.done())

    def operator_reset(self):
        # Explicit existing operator confirmation; never called automatically.
        if not self.recovery_ready():
            raise RuntimeError('Unresolved unload response; restart bridge after mechanism inspection')
        self.pending = None
        self.uncertain = False
        self._stop_sent = False
        self._stop_error = None
