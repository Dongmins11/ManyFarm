"""예찰 촬영은 태그 이벤트 대기 없이 기존 도착 시각 이후 프레임을 요청한다."""
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
SRC=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(SRC/'scout_robot'),str(SRC/'farm_navigation')]
from scout_new.states.segment_progress_state import SegmentProgressState

class NoWaitCapture(unittest.TestCase):
    def test_capture_never_waits_for_tag_or_restarts_lease(self) -> None:
        events=[]
        def forbidden(*args: object) -> None:
            self.fail('촬영 중 태그 사용권/적용 대기는 허용하지 않음')
        control=NS(begin=forbidden,end=forbidden,wait_applied=forbidden)
        def call(*args: object,**kwargs: object) -> dict:
            events.append(kwargs['after_stamp_ns'])
            return {}
        context=NS(worker=NS(call=call),stamp=100,camera_session='cam')
        node=NS(_tag_control=control,check=lambda:None,_navigator=NS(stationary_now=lambda:True))
        SegmentProgressState(NS(context=context,node=node),None)._capture()
        self.assertEqual(events,[100])

    def test_moving_capture_is_rejected(self) -> None:
        context=NS(worker=NS(call=lambda *a,**k:{}),stamp=100,camera_session='cam')
        node=NS(check=lambda:None,_navigator=NS(stationary_now=lambda:False))
        with self.assertRaisesRegex(RuntimeError,'moved'):
            SegmentProgressState(NS(context=context,node=node),None)._capture()
