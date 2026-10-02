"""실물 어댑터의 시각·좌표·움직임 거절 검사. 실제 카메라/모터는 실행하지 않습니다."""
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import pytest
from scout_new.real_observer import RealObserver
from scout_new.observer import SurveyObserver


def observer(stopped=True):
    obj=RealObserver.__new__(RealObserver)
    obj._capture_stamp=None
    obj._node=NS(_vcfg={'camera_frame':'camera'},lookup=lambda *_:np.eye(4),
        get_clock=lambda:NS(now=lambda:NS(nanoseconds=200)),
        _navigator=NS(stationary_now=lambda:stopped))
    return obj


def test_stationary_reference_and_annotation_stamp():
    obj=observer()
    with patch.object(SurveyObserver,'call',return_value={'metadata':{}}):
        data=obj.call('capture',lambda:None,after_stamp_ns=100)
        assert data['metadata']['stamp_ns']==200
        np.testing.assert_allclose(data['metadata']['T_map_camera_reference'],np.eye(4))
        with pytest.raises(ValueError,match='mismatch'):
            obj.call('annotate',lambda:None,stamp_ns=100)
        obj.call('annotate',lambda:None,stamp_ns=200)


def test_motion_and_old_stop_are_rejected():
    with patch.object(SurveyObserver,'call',return_value={'metadata':{}}):
        with pytest.raises(RuntimeError):observer(False).call('capture',lambda:None,after_stamp_ns=100)
        with pytest.raises(RuntimeError):observer().call('capture',lambda:None,after_stamp_ns=300)
