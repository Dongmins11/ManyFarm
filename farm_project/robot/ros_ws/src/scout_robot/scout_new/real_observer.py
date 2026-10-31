"""실물 정지 관측 어댑터. 노출 시각 대신 관측 구간의 TF 안정성을 검사합니다."""
from farm_navigation.operation_clock import operation_time
from typing import Callable, Any
from pathlib import Path
import threading
import time
import numpy as np
from .observer import SurveyObserver


class RealObserver(SurveyObserver):
    def __init__(self, command: list[str], log: Path, node: Any) -> None:
        super().__init__(command,log,clock=lambda: operation_time(node))
        self._node=node
        self._rpc_timeout=float(node._vcfg.get("rpc_timeout_s",180))
        self._capture_stamp=None

    def call(self, op: str, check: Callable[[],None], **values: object) -> dict:
        if op=='annotate':
            if values.get('stamp_ns')!=self._capture_stamp:raise ValueError('Annotation capture mismatch')
            return super().call(op,check,**values)
        if op not in ('info','capture'):return super().call(op,check,**values)
        frame=self._node._vcfg['camera_frame']
        reference=self._node.lookup('map',frame,0)
        stamp=self._node.get_clock().now().nanoseconds
        if stamp<=int(values.get('after_stamp_ns',0)):raise RuntimeError('관측 기준 시각이 정지 시각보다 늦어야 합니다.')
        done=threading.Event();errors=[]
        last_check=[operation_time(self._node)]
        def monitor() -> None:
            while not done.is_set():
                try:
                    check()
                    if operation_time(self._node)-last_check[0]>.25:
                        raise RuntimeError('관측 TF 감시 간격 초과: 결과 폐기')
                    current=self._node.lookup('map',frame,0)
                    angle=np.arccos(np.clip((np.trace(reference[:3,:3].T@current[:3,:3])-1)/2,-1,1))
                    if np.linalg.norm(reference[:3,3]-current[:3,3])>.01 or angle>.01 or not self._node._navigator.stationary_now():
                        raise RuntimeError('관측 중 로봇/카메라 움직임: 결과 폐기')
                    last_check[0]=operation_time(self._node)
                except Exception as error:
                    errors.append(error);return
                done.wait(.05)
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        try:
            result=super().call(op,check,**values)
        finally:
            done.set();thread.join(timeout=5)
        if thread.is_alive():raise RuntimeError('관측 TF 감시 종료 실패')
        if errors:raise errors[0]
        current=self._node.lookup('map',frame,0)
        angle=np.arccos(np.clip((np.trace(reference[:3,:3].T@current[:3,:3])-1)/2,-1,1))
        if operation_time(self._node)-last_check[0]>.25 or np.linalg.norm(reference[:3,3]-current[:3,3])>.01 or angle>.01 or not self._node._navigator.stationary_now():
            raise RuntimeError('관측 종료 위치/정지 확인 실패: 결과 폐기')
        result['metadata']['stamp_ns']=stamp
        result['metadata']['T_map_camera_reference']=reference.tolist()
        if op=='capture':self._capture_stamp=stamp
        return result
