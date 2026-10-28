"""가상 투입은 실제 분리 과실만 이동하고 원래 ID를 유지해야 한다."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices'))
from farm_sim_devices.fruit_attachment import FruitAttachments


class TransferTests(unittest.TestCase):
    def make(self) -> FruitAttachments:
        obj=FruitAttachments.__new__(FruitAttachments)
        obj.paths=['/existing/red','/existing/yellow']
        obj.attached=np.array([True,False]);obj.active=np.array([False,True]);obj.timer=np.ones(2)
        obj._cached_positions=np.zeros((2,3));obj._cached_orientations=np.tile([1.,0,0,0],(2,1))
        self.calls=[]
        obj.set_active=lambda indices:self.calls.append(('active',indices.copy()))
        obj.view=SimpleNamespace(set_world_poses=lambda **kw:self.calls.append(('pose',kw)),
            set_velocities=lambda values,**kw:self.calls.append(('velocity',values.copy(),kw)))
        return obj

    def test_attached_fruit_rejected_without_fixture(self) -> None:
        obj=self.make()
        with self.assertRaisesRegex(ValueError,'수확되지 않은'):
            obj.relocate_detached(['/existing/red'],np.array([[1,2,3]]),np.array([[1,0,0,0]]))
        self.assertTrue(obj.attached[0]);self.assertEqual(self.calls,[])

    def test_detached_identity_and_non_target_preserved(self) -> None:
        obj=self.make();paths=obj.paths.copy()
        obj.relocate_detached(['/existing/yellow'],np.array([[1,2,3]]),np.array([[1,0,0,0]]))
        self.assertEqual(obj.paths,paths)
        self.assertTrue(obj.attached[0])
        np.testing.assert_array_equal(obj._cached_positions,[[0,0,0],[1,2,3]])
        np.testing.assert_array_equal(self.calls[1][1]['indices'],[1])

    def test_invalid_pose_cannot_detach_fixture(self) -> None:
        obj=self.make()
        with self.assertRaises(ValueError):
            obj.relocate_detached(['/existing/red'],np.array([[np.nan,2,3]]),np.array([[1,0,0,0]]),fixture=True)
        self.assertTrue(obj.attached[0]);self.assertEqual(self.calls,[])

    def test_duplicate_fruit_rejected(self) -> None:
        obj=self.make()
        with self.assertRaises(ValueError):
            obj.relocate_detached(['/existing/yellow']*2,np.zeros((2,3)),np.tile([1,0,0,0],(2,1)))
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main()
