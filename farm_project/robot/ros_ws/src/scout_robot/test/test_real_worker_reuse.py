"""장치 없이 취소 시점·RPC 응답 상태별 워커 수명을 검증한다."""
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scout_new.observer import SurveyObserver
from scout_new.real_observer import RealObserver
from scout_new.vision_runtime import VisionRuntime


class WorkerReuseTests(unittest.TestCase):
    def worker(self) -> RealObserver:
        worker = RealObserver.__new__(RealObserver)
        worker._rpc_clean = True
        worker._process = NS(poll=lambda: None)
        worker._responses = queue.Queue()
        return worker

    def test_cancel_before_send_keeps_worker_clean(self) -> None:
        worker = self.worker()
        with patch.object(SurveyObserver, 'call') as send:
            with self.assertRaisesRegex(RuntimeError, 'cancel'):
                worker._call_worker('capture', Mock(side_effect=RuntimeError('cancel')))
            send.assert_not_called()
        self.assertTrue(worker.reusable)

    def test_interrupted_rpc_is_not_reused_or_sent_again(self) -> None:
        worker = self.worker()
        with patch.object(SurveyObserver, 'call', side_effect=TimeoutError('timeout')) as send:
            with self.assertRaises(TimeoutError):
                worker._call_worker('capture', lambda: None)
            with self.assertRaisesRegex(RuntimeError, '상태 불확실'):
                worker._call_worker('capture', lambda: None)
            self.assertEqual(send.call_count, 1)
        self.assertFalse(worker.reusable)

    def test_pending_response_and_dead_process_disallow_reuse(self) -> None:
        worker = self.worker()
        with patch.object(SurveyObserver, 'call', return_value={'ok': True}):
            worker._call_worker('capture', lambda: None)
        self.assertTrue(worker.reusable)
        worker._responses.put({'late': True})
        self.assertFalse(worker.reusable)
        worker._responses.get()
        worker._process = NS(poll=lambda: 1)
        self.assertFalse(worker.reusable)

    def test_real_failure_reuses_only_clean_rpc_and_keeps_sim_policy(self) -> None:
        for backend, clean, expected_close in [('realsense_legacy', True, False),
                                               ('realsense_legacy', False, True),
                                               ('sim', True, True)]:
            with self.subTest(backend=backend, clean=clean):
                runtime = VisionRuntime.__new__(VisionRuntime)
                runtime._node = NS(_vcfg={'backend': backend}, _shutdown_requested=False,
                                   get_logger=lambda: NS(info=lambda _: None))
                worker = NS(reusable=clean, close=Mock())
                runtime._worker = worker
                runtime._lock = threading.Lock()
                runtime._closed = threading.Event()
                runtime._io = NS(submit=Mock())
                runtime._leased = True
                runtime.release(False)
                self.assertEqual(worker.close.called, expected_close)
                self.assertEqual(runtime._io.submit.called, expected_close)


if __name__ == '__main__':
    unittest.main()
