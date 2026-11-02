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
        w._call_worker=Mock(side_effect=lambda *a,**k:{'metadata':{'session':'cam'},'acquisition_id':7})
        return w

    def test_inference_delay_and_odom_uncertainty_do_not_discard_capture(self):
        w=self.worker()
        def rpc(op,*a,**k):
            if op=='capture':
                self.assertEqual(k['acquisition_id'],7)
                w._node._navigator.stationary_now.return_value=False
                time.sleep(.15)
            return {'metadata':{'session':'cam'},'acquisition_id':7}
        w._call_worker.side_effect=rpc
        result=w.call('capture',lambda:None,after_stamp_ns=1)
        self.assertEqual(w._node.lookup.call_count,1)
        self.assertEqual([c.args[0] for c in w._call_worker.call_args_list],['acquire','capture'])
        self.assertEqual(result['metadata']['stamp_ns'],100)
        self.assertEqual(result['metadata']['T_map_camera_reference'],np.eye(4).tolist())

    def test_amcl_change_after_capture_does_not_trigger_new_lookup(self):
        w=self.worker();moved=np.eye(4);moved[0,3]=.03
        w._node.lookup.side_effect=[np.eye(4),moved]
        result=w.call('capture',lambda:None)
        self.assertEqual(w._node.lookup.call_count,1)
        self.assertEqual(result['metadata']['T_map_camera_reference'],np.eye(4).tolist())

    def test_movement_during_acquisition_recaptures_before_inference(self):
        w=self.worker();attempts=[]
        def rpc(op,*a,**k):
            attempts.append(op)
            if attempts==['acquire']:
                w._node._navigator.stationary_now.side_effect=[False,True,True,True,True,True]
            return {'metadata':{'session':'cam'},'acquisition_id':7}
        w._call_worker.side_effect=rpc
        w.call('capture',lambda:None)
        self.assertEqual(attempts,['acquire','acquire','capture'])

    def test_same_stop_reuses_pose_and_new_stop_refreshes(self):
        w=self.worker(); epoch=[1]
        w._node._navigator.stationary_epoch=lambda:epoch[0]
        w.call('info',lambda:None)
        w.call('capture',lambda:None)
        self.assertEqual(w._node.lookup.call_count,1)
        epoch[0]=2
        w.call('capture',lambda:None)
        self.assertEqual(w._node.lookup.call_count,2)

    def test_large_localization_change_refreshes_pose(self):
        w=self.worker();w._node._navigator.stationary_epoch=lambda:1
        w.call('info',lambda:None)
        moved=np.eye(4);moved[0,3]=.2
        w._node._poses=NS(observation_latest=lambda *a:moved)
        w._node.lookup.return_value=moved
        result=w.call('capture',lambda:None)
        self.assertEqual(w._node.lookup.call_count,2)
        self.assertEqual(result['metadata']['T_map_camera_reference'],moved.tolist())

    def test_info_does_not_infer(self):
        w=self.worker();w.call('info',lambda:None)
        self.assertEqual([c.args[0] for c in w._call_worker.call_args_list],['info'])

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
