"""실물 관측 지연·TF 회복·재촬영·취소를 장치 없이 검증한다."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import sys
import time
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scout_new.real_observer import RealObserver
from farm_navigation.pose_provider import TransformUnavailable

class ObservationRecoveryTests(unittest.TestCase):
    def worker(self):
        w=RealObserver.__new__(RealObserver)
        w._node=NS(_vcfg={'camera_frame':'camera'},
            _navigator=NS(stationary_now=Mock(return_value=True)),
            lookup=Mock(return_value=np.eye(4)),
            get_logger=lambda:NS(warning=Mock()),
            get_clock=lambda:NS(now=lambda:NS(nanoseconds=100)))
        w._call_worker=Mock(side_effect=lambda *a,**k:{'metadata':{}})
        return w

    def test_slow_rpc_has_no_tf_queries_and_keeps_capture_reference(self):
        w=self.worker()
        def rpc(*a,**k):
            self.assertEqual(w._node.lookup.call_count,1)
            time.sleep(.30)  # 이전 0.25초 제한을 넘는 추론
            self.assertEqual(w._node.lookup.call_count,1)
            return {'metadata':{}}
        w._call_worker.side_effect=rpc
        result=w.call('capture',lambda:None,after_stamp_ns=1)
        self.assertEqual(w._node.lookup.call_count,2)
        self.assertEqual(result['metadata']['stamp_ns'],100)
        self.assertEqual(result['metadata']['T_map_camera_reference'],np.eye(4).tolist())

    def test_tf_unavailable_after_rpc_waits_without_repeating_rpc(self):
        w=self.worker()
        w._node.lookup.side_effect=[np.eye(4),TransformUnavailable('stale'),np.eye(4)]
        result=w.call('capture',lambda:None)
        self.assertEqual(w._call_worker.call_count,1)
        self.assertIn('T_map_camera_reference',result['metadata'])

    def test_changed_pose_discards_result_and_recaptures(self):
        w=self.worker(); moved=np.eye(4);moved[0,3]=.03
        w._node.lookup.side_effect=[np.eye(4),moved,moved,moved]
        result=w.call('capture',lambda:None)
        self.assertEqual(w._call_worker.call_count,2)
        self.assertEqual(result['metadata']['T_map_camera_reference'],moved.tolist())

    def test_wait_is_cancelable_and_does_not_start_rpc(self):
        w=self.worker();w._node.lookup.side_effect=TransformUnavailable('stale')
        check=Mock(side_effect=[None,RuntimeError('cancel')])
        with self.assertRaisesRegex(RuntimeError,'cancel'):w.call('capture',check)
        w._call_worker.assert_not_called()

    def test_invalid_transform_is_not_retried(self):
        w=self.worker();w._node.lookup.side_effect=ValueError('invalid quaternion')
        with self.assertRaises(ValueError):w.wait_ready(lambda:None)
        w._node.lookup.assert_called_once()

    def test_rpc_failure_is_not_hidden(self):
        w=self.worker();w._call_worker.side_effect=RuntimeError('worker exited')
        with self.assertRaisesRegex(RuntimeError,'worker exited'):w.call('capture',lambda:None)
        self.assertEqual(w._call_worker.call_count,1)

if __name__=='__main__':unittest.main()
