"""장치 없이 노드/미션 사이 영상 워커 소유권을 검증합니다."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'robot/ros_ws/src/scout_robot'))
from scout_new.vision_runtime import VisionRuntime


@pytest.mark.parametrize('backend', ['realsense_legacy', 'sim'])
def test_reuse_and_replace(tmp_path, backend):
    workers = []
    class Worker:
        def __init__(self, *args):
            self.is_alive = True
            self.closed = False
            workers.append(self)
        def receive(self, check, timeout):
            check()
            return {'ready': True}
        def close(self):
            self.closed = True
            self.is_alive = False
    node = NS(_root=tmp_path, _cfg={'output_dir':'runs', 'vision_config':'vision.json'},
              _vcfg={'backend':backend}, _python=Path(sys.executable), _shutdown_requested=False,
              get_parameter=lambda _: NS(value=False),
              get_logger=lambda: NS(info=lambda _:None, error=lambda _:None))
    with patch('scout_new.vision_runtime.RealObserver', Worker), patch('scout_new.vision_runtime.SurveyObserver', Worker):
        runtime = VisionRuntime(node)
        try:
            runtime._future.result(timeout=2)
            assert runtime.readiness_error == ''
            first = runtime.acquire()
            with pytest.raises(RuntimeError, match='사용 중'):
                runtime.acquire()
            runtime.release(True)
            assert runtime.acquire() is first
            assert not first.closed
            runtime.release(False)
            runtime._future.result(timeout=2)
            assert first.closed
            assert runtime.acquire() is not first
            runtime.release(True)
            workers[-1].is_alive = False
            assert '종료됨' in runtime.readiness_error
        finally:
            runtime.close()
        assert all(worker.closed for worker in workers)


def test_startup_failure_blocks_goal(tmp_path):
    node = NS(_root=tmp_path, _cfg={'output_dir':'runs','vision_config':'vision.json'},
              _vcfg={'backend':'realsense_legacy'}, _python=Path(sys.executable),
              _shutdown_requested=False, get_logger=lambda: NS(info=lambda _:None,error=lambda _:None))
    with patch('scout_new.vision_runtime.RealObserver', side_effect=RuntimeError('camera disconnected')):
        runtime = VisionRuntime(node)
        try:
            runtime._future.result(timeout=2)
            assert 'camera disconnected' in runtime.readiness_error
            with pytest.raises(RuntimeError, match='camera disconnected'):
                runtime.acquire()
        finally:
            runtime.close()
