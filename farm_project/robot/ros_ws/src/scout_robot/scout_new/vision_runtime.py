"""노드 수명의 영상 워커. 미션은 준비된 워커를 빌리고 반환합니다."""
from farm_navigation.operation_clock import operation_time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid
from typing import Any

from .observer import SurveyObserver
from .real_observer import RealObserver


class VisionRuntime:
    def __init__(self, node: Any) -> None:
        self._node = node
        self._lock = threading.Lock()
        self._io = ThreadPoolExecutor(max_workers=1, thread_name_prefix='vision_startup')
        self._worker = None
        self._closed = threading.Event()
        self._leased = False
        self._error = '영상 워커 준비 중'
        self.log_path = node._root / node._cfg['output_dir'] / ('vision_' + uuid.uuid4().hex[:12]) / 'vision_worker.log'
        self._future = self._io.submit(self._prepare)

    def _check(self) -> None:
        # 미션 취소와 독립적입니다. 노드 종료 때만 준비 작업을 중단합니다.
        if self._closed.is_set() or self._node._shutdown_requested:
            raise RuntimeError('영상 워커 준비 종료 요청')

    def _prepare(self) -> None:
        worker = None
        started = time.monotonic()
        try:
            self._check()
            node = self._node
            node.get_logger().info('영상 사전 준비 시작: 모델 로딩·카메라 워밍업')
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            real = node._vcfg.get('backend') == 'realsense_legacy'
            script = 'run_scout_real_worker.py' if real else 'run_scout_survey_worker.py'
            command = [str(node._python), str(node._root / 'scripts' / script),
                       '--config', str(node._root / node._cfg['vision_config'])]
            if not real:
                command += ['--device', str(node.get_parameter('device').value)]
                if node.get_parameter('headless').value:
                    command.append('--headless')
            worker = (RealObserver(command, self.log_path, node) if real else
                      SurveyObserver(command, self.log_path,
                          rpc_timeout_s=node._vcfg.get('rpc_timeout_s', 30.0), clock=lambda: operation_time(node)))
            if not worker.receive(self._check, float(node._vcfg.get('startup_timeout_s', 120))).get('ready'):
                raise RuntimeError('영상 워커 ready 응답 누락')
            self._check()
            with self._lock:
                self._worker = worker
                self._error = ''
            worker = None
            node.get_logger().info(f'영상 사전 준비 완료: Goal 수락 가능 ({time.monotonic()-started:.1f}초)')
        except Exception as error:
            if worker is not None:
                try:
                    worker.close()
                except Exception as cleanup_error:
                    error = RuntimeError(f'{error}; 종료 실패: {cleanup_error}')
            with self._lock:
                self._error = f'영상 준비 실패: {error}'
            self._node.get_logger().error(self._error)

    @property
    def readiness_error(self) -> str:
        with self._lock:
            if self._error:
                return self._error
            if self._worker is None or not self._worker.is_alive:
                return '영상 워커 종료됨: 노드 재시작 필요'
            return ''

    def acquire(self) -> SurveyObserver:
        error = self.readiness_error
        if error:
            raise RuntimeError(error)
        with self._lock:
            if self._leased:
                raise RuntimeError('영상 워커 사용 중')
            self._leased = True
            return self._worker

    def release(self, reusable: bool) -> None:
        # Controller의 단일 I/O 작업이 끝난 뒤 호출합니다.
        # 실물은 미션 결과 대신 RPC 동기화 상태로 판단합니다. 시뮬 정책은 유지합니다.
        if self._node._vcfg.get('backend') == 'realsense_legacy':
            reusable = self._worker is not None and self._worker.reusable
            self._node.get_logger().info('영상 워커 반환: ' +
                ('정상 RPC 상태, 재사용' if reusable else 'RPC/프로세스 상태 불확실, 재준비'))
        with self._lock:
            self._leased = False
            if reusable:
                return
            self._error = '영상 워커 재준비 중'
            worker, self._worker = self._worker, None
        if worker is not None:
            worker.close()
        if not self._closed.is_set() and not self._node._shutdown_requested:
            self._future = self._io.submit(self._prepare)

    def close(self) -> None:
        self._closed.set()
        self._io.shutdown(wait=True)
        with self._lock:
            worker, self._worker = self._worker, None
        if worker is not None:
            worker.close()
