"""실물 정지 관측: 정지 프레임 확보와 추론을 분리하고 확보 구간의 기준 TF를 고정한다."""
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
                    epoch_fn = getattr(self._node._navigator, 'stationary_epoch', None)
                    epoch = epoch_fn() if epoch_fn else None
                    cached = getattr(self, '_pose_cache', None)
                    # 공통 조회의 무한 대기에 들어가기 전에 같은 정지 구간의 기준을 사용한다.
                    if cached is not None and epoch is not None and cached[0] == epoch:
                        provider = getattr(self._node, '_poses', None)
                        fresh = provider.observation_latest('map', frame) if provider else None
                        if fresh is not None:
                            distance = float(np.linalg.norm(fresh[:3, 3]-cached[1][:3, 3]))
                            cosine = np.clip((np.trace(fresh[:3, :3] @ cached[1][:3, :3].T)-1)/2, -1, 1)
                            angle = float(np.arccos(cosine))
                            if (distance > float(self._node._vcfg.get('reference_reset_distance_m', .10)) or
                                    angle > float(self._node._vcfg.get('reference_reset_angle_rad', .0872664626))):
                                self._pose_cache = None
                                continue
                        check()
                        if epoch_fn() == epoch:
                            return cached[1].copy()
                        self._pose_cache = None
                        continue
                    self._pose_cache = None
                    pose = self._node.lookup('map', frame, 0)
                    check()
                    if self._node._navigator.stationary_now():
                        if epoch is not None:
                            if epoch_fn() != epoch:
                                continue
                            self._pose_cache = (epoch, pose.copy())
                        return pose
                except TransformUnavailable as error:
                    reason = str(error)
            self._pose_cache = None
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
            total_started = time.monotonic()
            reference = self.wait_ready(check)
            ready_elapsed = time.monotonic()-total_started
            acquire_started = time.monotonic()
            stamp = self._node.get_clock().now().nanoseconds
            if stamp <= int(values.get('after_stamp_ns', 0)):
                raise RuntimeError('관측 기준 시각이 정지 시각보다 늦어야 합니다.')
            done = threading.Event()
            uncertain = threading.Event()

            def monitor() -> None:
                # 프레임 확보·저장 RPC 동안만 정지를 확인한다. 추론은 감시하지 않는다.
                while not done.is_set():
                    if not self._node._navigator.stationary_now():
                        uncertain.set()
                    done.wait(.05)

            thread = threading.Thread(target=monitor, daemon=True)
            thread.start()
            try:
                result = self._call_worker('acquire' if op == 'capture' else 'info', check, **values)
                if not self._node._navigator.stationary_now():
                    uncertain.set()
            finally:
                done.set()
                thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError('촬영 정지 감시 종료 실패')
            acquire_elapsed = time.monotonic()-acquire_started
            if uncertain.is_set():
                self._pose_cache = None
                self._node.get_logger().warning('관측 재촬영: 프레임 확보 구간의 정지 확인 실패')
                check()
                continue
            inference_started = time.monotonic()
            if op == 'capture':
                # 동일 프레임만 추론한다. 다른 요청/이전 프레임의 재사용을 토큰으로 차단한다.
                result = self._call_worker('capture', check,
                    acquisition_id=result['acquisition_id'], session=result['metadata']['session'])
            # D435 노출 시각은 ROS에 동기화되지 않는다. 실제 정지가 확인된
            # 확보 구간 시작의 TF를 사용하며, 이후 AMCL 보정과 비교해 폐기하지 않는다.
            result['metadata']['observation_timing_s'] = {
                'ready': ready_elapsed, 'acquire': acquire_elapsed,
                'inference': time.monotonic()-inference_started,
                'total': time.monotonic()-total_started}
            logger = self._node.get_logger()
            if hasattr(logger, 'info'):
                logger.info('OBS_TIMING ' + str(result['metadata']['observation_timing_s']))
            result['metadata']['stamp_ns'] = stamp
            result['metadata']['T_map_camera_reference'] = reference.tolist()
            result['metadata']['pose_reference_policy'] = 'stationary_acquisition_start_not_exposure'
            if op == 'capture':
                self._capture_stamp = stamp
            return result
