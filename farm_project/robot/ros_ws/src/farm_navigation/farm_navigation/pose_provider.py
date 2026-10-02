"""TF 조회 어댑터. 위치추정기를 구현하거나 TF를 발행하지 않습니다."""
from collections.abc import Callable
import time
import numpy as np
from numpy.typing import NDArray
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener, TransformException
from .navigation_types import NavigationSettings


class PoseProvider:
    def __init__(self, node: Node, settings: NavigationSettings) -> None:
        self._node: Node = node
        self._settings: NavigationSettings = settings
        self._buffer: Buffer = Buffer(cache_time=Duration(seconds=30))
        self._listener: TransformListener = TransformListener(self._buffer,node)

    def lookup(self, target: str, source: str, stamp_ns: int, check: Callable[[],None]) -> NDArray[np.float64]:
        """stamp=0은 최신 위치, 양수는 촬영 등 특정 ROS 시각의 변환입니다."""
        end=time.monotonic()+self._settings.tf_timeout_s
        error: Exception | None = None
        while time.monotonic()<end:
            check()
            try:
                message=self._buffer.lookup_transform(target,source,Time(nanoseconds=int(stamp_ns)))
                stamp=message.header.stamp.sec*10**9+message.header.stamp.nanosec
                if stamp_ns==0 and stamp!=0:
                    age=(self._node.get_clock().now().nanoseconds-stamp)/1e9
                    if age<0 or age>self._settings.tf_max_age_s:
                        raise RuntimeError('최신 위치 TF가 오래되었거나 미래 시각입니다.')
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
                time.sleep(.02)
        raise RuntimeError(f'TF 조회 실패: {target} ← {source}, stamp={stamp_ns}: {error}')

    def current(self, check: Callable[[],None]) -> NDArray[np.float64]:
        return self.lookup(self._settings.map_frame,self._settings.base_frame,0,check)

    def close(self) -> None:
        self._listener.unregister()
