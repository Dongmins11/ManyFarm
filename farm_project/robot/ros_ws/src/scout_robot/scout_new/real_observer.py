"""실물 정지 관측: TF는 관측 전후에 확보하고 추론 중에는 odom 정지만 감시한다."""
from typing import Callable, Any
from pathlib import Path
import threading
import time
import numpy as np
from .observer import SurveyObserver


class RealObserver(SurveyObserver):
    def __init__(self, command: list[str], log: Path, node: Any) -> None:
        self._rpc_clean = True
        super().__init__(command,log)
        self._node=node
        self._rpc_timeout=float(node._vcfg.get("rpc_timeout_s",180))
        self._capture_stamp=None

    @property
    def reusable(self) -> bool:
        """RPC 성공 응답을 모두 읽었고 살아 있는 워커만 재사용합니다."""
        return self._rpc_clean and self.is_alive and self._responses.empty()

    def _call_worker(self, op: str, check: Callable[[], None], **values: object) -> dict:
        # 전송 전 취소는 연결을 손상시키지 않습니다. 전송 이후 예외는 교체 대상입니다.
        check()
        if not self._rpc_clean:
            raise RuntimeError('영상 RPC 상태 불확실: 워커 교체 필요')
        self._rpc_clean = False
        result = super().call(op, check, **values)
        self._rpc_clean = True
        return result

    def wait_ready(self, check: Callable[[], None]) -> np.ndarray:
        """I/O 스레드에서 정상 TF·정지를 기다린다. 취소 시 즉시 예외를 전달한다."""
        from farm_navigation.pose_provider import TransformUnavailable
        frame = self._node._vcfg['camera_frame']
        next_log = 0.0
        while True:
            check()
            reason = '정지 odom 수신 대기'
            if self._node._navigator.stationary_now():
                try:
                    pose = self._node.lookup('map', frame, 0)
                    check()
                    if self._node._navigator.stationary_now():
                        return pose
                except TransformUnavailable as error:
                    reason = str(error)
            if time.monotonic() >= next_log:
                self._node.get_logger().warning('관측/주행 재개 대기: ' + reason)
                next_log = time.monotonic() + 5.0
            time.sleep(.05)

    def call(self, op: str, check: Callable[[],None], **values: object) -> dict:
        if op == 'annotate':
            if values.get('stamp_ns') != self._capture_stamp:
                raise ValueError('Annotation capture mismatch')
            return self._call_worker(op, check, **values)
        if op not in ('info', 'capture'):
            return self._call_worker(op, check, **values)
        while True:
            reference = self.wait_ready(check)
            stamp = self._node.get_clock().now().nanoseconds
            if stamp <= int(values.get('after_stamp_ns', 0)):
                raise RuntimeError('관측 기준 시각이 정지 시각보다 늦어야 합니다.')
            done = threading.Event()
            uncertain = threading.Event()

            def monitor() -> None:
                # 추론 시간과 스레드 스케줄링 지연을 TF 오류로 취급하지 않는다.
                # odom 정지가 불확실했던 관측은 응답을 소진한 후 재촬영한다.
                while not done.is_set():
                    if not self._node._navigator.stationary_now():
                        uncertain.set()
                    done.wait(.05)

            thread = threading.Thread(target=monitor, daemon=True)
            thread.start()
            try:
                result = self._call_worker(op, check, **values)
            finally:
                done.set()
                thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError('관측 감시 종료 실패')
            # 촬영 기준 TF를 최신 TF로 덮어쓰지 않는다. 정상 TF를 다시 받은 뒤
            # 전후 자세가 달라졌으면 해당 결과만 버리고 같은 위치에서 재관측한다.
            current = self.wait_ready(check)
            angle = np.arccos(np.clip((np.trace(reference[:3,:3].T @ current[:3,:3])-1)/2, -1, 1))
            if uncertain.is_set() or np.linalg.norm(reference[:3,3]-current[:3,3]) > .01 or angle > .01:
                self._node.get_logger().warning('관측 결과 재측정: 정지 불확실 또는 관측 전후 자세 변경')
                check()
                continue
            result['metadata']['stamp_ns'] = stamp
            result['metadata']['T_map_camera_reference'] = reference.tolist()
            if op == 'capture':
                self._capture_stamp = stamp
            return result
