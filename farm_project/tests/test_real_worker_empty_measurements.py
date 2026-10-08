"""실물 워커 RPC의 빈 측정·저장·후속 촬영을 검증합니다. 실제 장치는 사용하지 않습니다."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_scout_real_worker.py'
spec = importlib.util.spec_from_file_location('real_worker_under_test', SCRIPT)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

class WorkerTests(unittest.TestCase):
    def exercise(self, objects, camera_error=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'saved';config=root/'config.json'
            config.write_text(json.dumps(dict(legacy_directory=tmp,model='test.pt',camera={},camera_frame='camera',confidence=.6)))
            closed=[]
            class Camera:
                def __init__(self, config):pass
                def start(self):pass
                def close(self):closed.append(True)
                def capture(self, folder, count):
                    if camera_error:raise RuntimeError('Camera disconnected')
                    folder.mkdir();(folder/'rgb.png').write_bytes(b'test-image')
                    return dict(intrinsics=dict(fx=1,fy=1,ppx=0,ppy=0),rgb_size=[1280,720],white_balance=4000,auto_white_balance=True,auto_exposure=True,warmup_frames=1,requested_fps=6),{}
            valid=dict(xyz_m=[.1,.2,1.],confidence=.9,**{'class':'RIPE'},bbox_xyxy=[0,0,10,10])
            detector=NS(torch=NS(set_num_threads=lambda n:None),YOLO=lambda *a,**k:object())
            captures=iter([objects,[valid]])
            detector.detect_capture=lambda *a,**k:dict(objects=next(captures))
            def imwrite(path, image):Path(path).write_bytes(b'annotated');return True
            cv=NS(imread=lambda p:object(),imwrite=imwrite)
            requests=[dict(id=1,op='capture'),dict(id=2,op='annotate',directory=str(dest),labels=[]),dict(id=3,op='capture'),dict(op='stop')]
            output=io.StringIO();errors=io.StringIO();original_path=sys.path[:]
            try:
                with patch.dict(sys.modules,{'detect_capture':detector,'scout_realsense_camera':NS(ConfiguredCamera=Camera),'cv2':cv}),patch.object(sys,'argv',['worker','--config',str(config)]),patch.object(sys,'stdin',io.StringIO('\n'.join(map(json.dumps,requests)))),contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
                    worker.main()
            finally:sys.path[:]=original_path
            replies=[json.loads(line[9:]) for line in output.getvalue().splitlines() if line.startswith('FARM_RPC ')]
            saved=json.loads((dest/'measurement_status.json').read_text()) if (dest/'measurement_status.json').exists() else None
            self.assertEqual(closed,[True])
            return replies,saved

    def test_no_candidates_continues_and_saves_empty_observation(self):
        replies,saved=self.exercise([])
        self.assertTrue(replies[1]['ok']);self.assertEqual(saved['status'],'NO_DETECTIONS')
        self.assertTrue(replies[2]['ok']);self.assertTrue(replies[3]['ok'])

    def test_all_invalid_depth_continues_and_next_capture_still_works(self):
        obj=dict(xyz_m=None,confidence=.9)
        replies,saved=self.exercise([obj])
        self.assertTrue(replies[1]['ok']);self.assertEqual(replies[1]['result']['detections'],[])
        self.assertEqual(saved['status'],'NO_VALID_MEASUREMENTS');self.assertEqual(saved['rejected'],[obj])
        self.assertTrue(replies[2]['ok']);self.assertEqual(len(replies[3]['result']['detections']),1)

    def test_all_low_confidence_continues_without_coordinates(self):
        replies,saved=self.exercise([dict(xyz_m=[1,2,3],confidence=.2)])
        self.assertTrue(replies[1]['ok']);self.assertEqual(replies[1]['result']['detections'],[])
        self.assertEqual(saved['status'],'NO_VALID_MEASUREMENTS')

    def test_valid_detections_are_preserved(self):
        obj=dict(xyz_m=[1,2,3],confidence=.9,**{'class':'RIPE'},bbox_xyxy=[1,2,3,4])
        replies,saved=self.exercise([obj,dict(xyz_m=None,confidence=.9)])
        self.assertEqual(saved['status'],'VALID');self.assertEqual(saved['valid_count'],1)
        self.assertEqual(replies[1]['result']['detections'][0]['position_odom_m'],[1,2,3])

    def test_camera_failure_still_returns_rpc_failure(self):
        replies,saved=self.exercise([],camera_error=True)
        self.assertFalse(replies[1]['ok']);self.assertEqual(replies[1]['error'],'Camera disconnected')
        self.assertIsNone(saved)

if __name__=='__main__':unittest.main()
