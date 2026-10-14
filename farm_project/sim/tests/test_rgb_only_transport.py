"""RGB 전용 최적화 후 기존 RGB-D 독자의 NaN/깊이 데이터 호환을 검사한다."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'robot/ros_ws/src/farm_common'))
from farm_common import rgbd_shm as shm

class RgbOnlyTransportTests(unittest.TestCase):
    def test_rgb_only_full_depth_transitions_and_legacy_reader(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(shm,'location',lambda _:Path(directory)/'camera.bin'):
            writer=shm.RgbdWriter('test',4,3)
            legacy, rgb_reader=shm.RgbdReader('test'),shm.RgbdReader('test')
            rgb=np.arange(36,dtype=np.uint8).reshape(3,4,3)
            meta=dict(session='a',stamp_ns=123,aligned_depth=False,depth_definition='unavailable')
            try:
                for depth in (None,None,np.full((3,4),.75,np.float32),None):
                    info=meta if depth is None else dict(meta,aligned_depth=True,depth_definition='distance_to_image_plane')
                    self.assertTrue(writer.write(rgb,depth,info))
                    old,new=legacy.read(),rgb_reader.read(include_depth=False)
                    np.testing.assert_array_equal(old['rgb'],rgb)
                    np.testing.assert_array_equal(new['rgb'],rgb)
                    self.assertIsNone(new['depth'])
                    self.assertEqual(old['metadata'],new['metadata'])
                    if depth is None:self.assertTrue(np.isnan(old['depth']).all())
                    else:np.testing.assert_array_equal(old['depth'],depth)
                    self.assertIsNone(legacy.read())
            finally:writer.close()

    def test_missing_depth_requires_explicit_unavailable_metadata(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(shm,'location',lambda _:Path(directory)/'camera.bin'):
            writer=shm.RgbdWriter('test',4,3)
            try:
                with self.assertRaisesRegex(ValueError,'unavailable'):
                    writer.write(np.zeros((3,4,3),np.uint8),None,dict(session='a',stamp_ns=123))
            finally:writer.close()

if __name__=='__main__':unittest.main()
