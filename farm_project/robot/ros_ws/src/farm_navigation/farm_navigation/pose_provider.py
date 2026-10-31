"""TF 조회 어댑터. 위치추정기를 구현하거나 TF를 발행하지 않습니다."""
from farm_navigation.operation_clock import operation_time
from collections.abc import Callable
import time
import numpy as np
from numpy.typing import NDArray
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener, TransformException
from .navigation_types import NavigationSettings


class TransformUnavailable(RuntimeError):
    """TF 버퍼에 요청 시각이 아직 없거나 최신 자료가 만료됨. 유효성 오류와 구분."""


class TransformStale(TransformUnavailable):
    pass


class PoseProvider:
    def __init__(self, node: Node, settings: NavigationSettings) -> None:
        self._node: Node = node
        self._settings: NavigationSettings = settings
        self._buffer: Buffer = Buffer(cache_time=Duration(seconds=30))
        self._listener: TransformListener = TransformListener(self._buffer,node)

    def lookup(self, target: str, source: str, stamp_ns: int, check: Callable[[],None], *,
               on_unavailable: Callable[[Exception], None] | None = None) -> NDArray[np.float64]:
        """stamp=0은 최신 위치, 양수는 촬영 등 특정 ROS 시각의 변환입니다."""
        end=operation_time(self._node)+self._settings.tf_timeout_s
        error: Exception | None = None
        while operation_time(self._node)<end:
            check()
            try:
                message=self._buffer.lookup_transform(target,source,Time(nanoseconds=int(stamp_ns)))
                stamp=message.header.stamp.sec*10**9+message.header.stamp.nanosec
                if stamp_ns==0 and stamp!=0:
                    age=(self._node.get_clock().now().nanoseconds-stamp)/1e9
                    if age < 0:
                        raise RuntimeError('최신 위치 TF가 미래 시각입니다.')
                    if age > self._settings.tf_max_age_s:
                        raise TransformStale('최신 위치 TF가 오래되었습니다.')
                transform=message.transform
                q=transform.rotation
                quaternion=np.array([q.x,q.y,q.z,q.w],dtype=float)
                norm=float(np.linalg.norm(quaternion))
                if not np.isfinite(norm) or norm<1e-9:
                    raise ValueError('TF quaternion이 유효하지 않습니다.')
                x,y,z,w=quaternion/norm
                result=np.eye(4)
                result[:3,:3]=[
                    [1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                    [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                    [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],
                ]
                t=transform.translation
                result[:3,3]=[t.x,t.y,t.z]
                if not np.isfinite(result).all(): raise ValueError('TF 위치가 유효하지 않습니다.')
                return result
            except (TransformException,RuntimeError,ValueError) as exc:
                error=exc
                if on_unavailable is not None:
                    on_unavailable(exc)
                time.sleep(.02)
        kind = TransformUnavailable if isinstance(error, (TransformException, TransformUnavailable)) else RuntimeError
        raise kind(f'TF 조회 실패: {target} ← {source}, stamp={stamp_ns}: {error}') from error

    def lookup_available_pair(self, targets: tuple[str, str], source: str,
                              sample_stamp: Callable[[], int], check: Callable[[], None]
                              ) -> tuple[int, tuple[NDArray[np.float64], NDArray[np.float64]]]:
        """진행하는 표본 중 두 TF가 함께 존재하는 시각을 선택한다. 최신 TF로 대체하지 않는다."""
        deadline = operation_time(self._node) + self._settings.tf_timeout_s
        stamps: list[int] = []
        previous: int | None = None
        while operation_time(self._node) < deadline:
            check()
            stamp = int(sample_stamp())
            if stamp <= 0 or (previous is not None and stamp < previous):
                raise RuntimeError('기준 표본 시각이 유효하지 않거나 역행했습니다.')
            if previous != stamp:
                stamps.append(stamp)
            previous = stamp
            now = self._node.get_clock().now().nanoseconds
            stamps = [s for s in stamps if 0 <= now-s <= int(self._settings.tf_max_age_s*1e9)]
            for candidate in stamps:
                when = Time(nanoseconds=candidate)
                if not all(self._buffer.can_transform(t, source, when) for t in targets):
                    continue
                # 기존 lookup의 quaternion/유한값 검사를 그대로 사용한다.
                values = tuple(self.lookup(t, source, candidate, check) for t in targets)
                check()
                if not 0 <= self._node.get_clock().now().nanoseconds-candidate <= int(self._settings.tf_max_age_s*1e9):
                    raise TransformUnavailable('조회 완료 시 기준 표본이 오래되었습니다.')
                return candidate, values
            time.sleep(.02)
        details = {
            'targets': targets,
            'source': source,
            'tf_timeout_s': self._settings.tf_timeout_s,
            'tf_max_age_s': self._settings.tf_max_age_s,
            'last_sample_ns': previous,
            'retained_samples': len(stamps),
        }
        now_ns = self._node.get_clock().now().nanoseconds
        if previous is not None:
            details['sample_age_s'] = (now_ns-previous)/1e9
            when = Time(nanoseconds=previous)
            for target in targets:
                details[target] = self._buffer.can_transform(
                    target, source, when, return_debug_tuple=True)
        details['buffer_frames'] = self._buffer.all_frames_as_yaml()
        raise TransformUnavailable('기준 저장 실패 상세: '+str(details))


    def latest_sample(self):
        """등록 보고용 원본 TF와 샘플 시각을 반환한다. 캐시를 새 시각으로 포장하지 않는다."""
        return self._buffer.lookup_transform(self._settings.map_frame, self._settings.base_frame, Time())

    def current(self, check: Callable[[],None]) -> NDArray[np.float64]:
        return self.lookup(self._settings.map_frame,self._settings.base_frame,0,check)

    def recovery_ready(self) -> bool:
        """직전 0.1초의 map→base TF가 실제로 연결될 때만 복구를 허용합니다."""
        now = self._node.get_clock().now().nanoseconds
        try:
            self._buffer.lookup_transform(
                self._settings.map_frame, self._settings.base_frame,
                Time(nanoseconds=max(1, now - 100_000_000)))
            return True
        except TransformException:
            return False

    def close(self) -> None:
        self._listener.unregister()
