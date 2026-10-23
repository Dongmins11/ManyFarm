"""명시 선택한 차체 시험. 팔/배출 및 DockTransfer 성공을 모사하지 않는다."""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from .handoff_input_trace import InputTrace, traced


class BodyTrial:
    """진입 완료 후 소유권을 유지한다. 복귀는 별도 명시 요청으로만 시작한다."""
    def __init__(self, node: Any) -> None:
        from std_srvs.srv import Trigger
        self.node = node
        self.runtime = node.handoff_runtime
        self.body = None
        self.token = None
        self.phase = 'IDLE'
        self.detail = ''
        self.cancel = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='body_trial')
        self.services = []
        for operation in ('enter', 'restore', 'stop', 'status'):
            self.services.append(node.create_service(Trigger, 'handoff/body_trial/'+operation,
                lambda req, res, op=operation: self.request(op, res), callback_group=node.callbacks))
        self.timer = node.create_timer(.1, self.shutdown_check, callback_group=node.callbacks)

    def request(self, operation: str, response: Any) -> Any:
        with self.node.lock:
            try:
                if operation == 'status':
                    response.success = True
                elif operation == 'enter':
                    if (self.phase != 'IDLE' or self.node.busy or self.node.blocked
                            or self.node.stopping):
                        raise RuntimeError(f'STATE_NOT_IDLE: phase={self.phase}, busy={self.node.busy}, blocked={self.node.blocked}, stopping={self.node.stopping}')
                    report = self.runtime.readiness()
                    if not report['ready']:
                        raise RuntimeError(json.dumps(report, ensure_ascii=False))
                    self.detail = ''
                    token = 'body-trial-'+uuid.uuid4().hex
                    if not self.node.handoff.reserve('transfer', token, preempt=False, interruptible=False):
                        raise RuntimeError('다른 실행이 차체를 사용 중입니다.')
                    self.token = token
                    self.node.busy = True
                    self.phase = 'ENTERING'
                    self.pool.submit(self.run, 'enter')
                    response.success = True
                elif operation == 'restore':
                    if self.phase != 'ENTERED' or self.node.stopping:
                        raise RuntimeError('진입 완료 상태에서만 복귀할 수 있습니다.')
                    self.detail = ''
                    self.phase = 'RESTORING'
                    self.pool.submit(self.run, 'restore')
                    response.success = True
                elif operation == 'stop':
                    if self.token is None:
                        raise RuntimeError('차체 시험 실행 없음')
                    self.request_stop()
                    response.success = True
                else:
                    raise ValueError('알 수 없는 시험 요청')
                response.message = json.dumps({'test_only': True, 'phase': self.phase,
                    'detail': self.detail, 'request_accepted_only': operation != 'status'}, ensure_ascii=False)
            except Exception as error:
                response.success = False
                self.detail = str(error)
                response.message = json.dumps({'test_only': True, 'phase': self.phase,
                    'detail': self.detail, 'request_accepted_only': False}, ensure_ascii=False)
                self.node.get_logger().error('BODY_TRIAL_REJECTED '+response.message)
        return response

    def request_stop(self) -> None:
        # 호출자는 node.lock을 확보한다. 이동 작업의 check는 즉시 cancel을 관측한다.
        if not self.cancel.is_set():
            self.cancel.set()
            self.runtime.stop_output()
            self.phase = 'STOPPING'
            self.pool.submit(self.run, 'stop')

    def shutdown_check(self) -> None:
        with self.node.lock:
            if self.node.stopping and self.token is not None:
                self.request_stop()

    def wait(self, ticket: Any, *, stopping: bool = False) -> None:
        deadline = time.monotonic() + (30 if stopping else 240)
        while not ticket.done():
            if not stopping and self.cancel.is_set():
                raise RuntimeError('차체 시험 취소')
            if time.monotonic() > deadline:
                raise TimeoutError('차체 시험 완료 시간 초과')
            time.sleep(.02)
        ticket.result()

    @traced
    def run(self, operation: str) -> None:
        try:
            if operation == 'stop' and self.token is None:
                return
            if operation == 'enter':
                self.node.handoff.acquire('transfer', self.token, self.runtime.check)
                self.body = self.runtime.build_body()
            if self.body is not None:
                self.wait(self.body.start(operation), stopping=operation == 'stop')
            if operation == 'enter':
                with self.node.lock:
                    if not self.cancel.is_set(): self.phase = 'ENTERED'
                return
            self.finish(operation == 'restore' and not self.cancel.is_set(), '')
        except Exception as error:
            detail = str(error)
            self.cancel.set()
            try:
                if self.body is not None:
                    self.wait(self.body.start('stop'), stopping=True)
            except Exception as stop_error:
                detail += '; 정지 미확인: '+str(stop_error)
            self.finish(False, detail)

    def finish(self, success: bool, detail: str) -> None:
        self.runtime.stop_output()
        try:
            if self.body is not None: self.body.close()
        except Exception as error:
            success = False
            detail += '; 종료: '+str(error)
        with self.node.lock:
            self.phase = 'COMPLETED' if success else 'RECOVERY_REQUIRED'
            self.detail = detail
            if not success: self.node.blocked = True
            self.node.handoff.release('transfer', self.token)
            self.token = None
            self.node.busy = False
        self.node.get_logger().info('BODY_TRIAL '+json.dumps(
            {'phase': self.phase, 'detail': detail, 'arm_tested': False}, ensure_ascii=False))

    def close(self) -> None:
        self.pool.shutdown(wait=True)
        self.node.destroy_timer(self.timer)
        for service in self.services: self.node.destroy_service(service)
