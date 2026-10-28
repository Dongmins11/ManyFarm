"""벽 시험 전용 실행기 수명 관리. 콜백 스레드를 먼저 끝내고 객체를 제거한다."""
import threading
import time

class ManagedSpin:
    def __init__(self, executor):
        self.executor = executor
        self.stop = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            while not self.stop.is_set():
                self.executor.spin_once(timeout_sec=0.05)
        except Exception as error:
            self.error = error
            self.stop.set()

    def check(self):
        if self.error is not None:
            raise RuntimeError('벽 시험 콜백 실패: ' + repr(self.error)) from self.error
        if not self.thread.is_alive():
            raise RuntimeError('벽 시험 콜백 스레드가 종료되었습니다')

    def request_stop(self):
        self.stop.set()
        self.executor.wake()

    def join(self, timeout=None):
        self.thread.join(timeout)

    def is_alive(self):
        return self.thread.is_alive()


def start_spin(executor):
    # ThreadPoolExecutor가 객체 제거 뒤까지 작업을 보유하지 않도록 단일 실행기만 사용.
    from rclpy.executors import SingleThreadedExecutor
    if not isinstance(executor, SingleThreadedExecutor):
        raise TypeError('벽 시험은 SingleThreadedExecutor가 필요합니다')
    return ManagedSpin(executor)


def drain_then_close(executor, thread, closers, timeout=5.):
    if not isinstance(thread, ManagedSpin):
        raise TypeError('관리되지 않는 spin 스레드: 객체 제거 생략')
    deadline = time.monotonic() + timeout
    thread.request_stop()
    thread.join(timeout=max(0., deadline-time.monotonic()))
    if thread.is_alive():
        raise RuntimeError('spin 스레드 종료 미확인: 연결 객체 제거 생략')
    if not executor.shutdown(timeout_sec=max(0., deadline-time.monotonic())):
        raise RuntimeError('콜백 실행기 종료 미확인: 연결 객체 제거 생략')
    errors = []
    if thread.error is not None:
        errors.append('콜백 실패: ' + repr(thread.error))
    for close in closers:
        try:
            close()
        except Exception as error:
            errors.append(repr(error))
    if errors:
        raise RuntimeError('종료 검사 실패: ' + '; '.join(errors))
