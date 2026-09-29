"""USD-only checks: collision repair scope and original-layer preservation."""
import sys
from pathlib import Path
import unittest
from pxr import Usd,UsdGeom,UsdPhysics
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.bed_collisions import ensure_bed_collisions

class BedCollisions(unittest.TestCase):
    def test_repairs_only_beds_and_never_writes_root(self):
        s=Usd.Stage.CreateInMemory();UsdGeom.Xform.Define(s,'/World/farm_framechanged')
        paths=[]
        for group in ['GrowBed_01','Bed_Edge_1__1','Bed_Edge_1_1','Floor_CollisionCandidate','Cover_Side','Tree_01']:
            paths.append('/World/farm_framechanged/'+group+'/Mesh')
            UsdGeom.Mesh.Define(s,paths[-1])
        UsdPhysics.CollisionAPI.Apply(s.GetPrimAtPath(paths[1])).CreateCollisionEnabledAttr(False)
        UsdPhysics.CollisionAPI.Apply(s.GetPrimAtPath(paths[2])).CreateCollisionEnabledAttr(True)
        UsdPhysics.MeshCollisionAPI.Apply(s.GetPrimAtPath(paths[2])).CreateApproximationAttr('none')
        original=s.GetRootLayer().ExportToString();result=ensure_bed_collisions(s)
        self.assertEqual((result['added'],result['enabled'],result['existing']),(1,1,1))
        self.assertEqual(s.GetRootLayer().ExportToString(),original)
        self.assertEqual(s.GetEditTarget().GetLayer(),s.GetRootLayer())
        for path in paths[:3]:self.assertTrue(UsdPhysics.CollisionAPI(s.GetPrimAtPath(path)).GetCollisionEnabledAttr().Get())
        for path in paths[3:]:self.assertFalse(s.GetPrimAtPath(path).HasAPI(UsdPhysics.CollisionAPI))
        self.assertEqual(UsdPhysics.MeshCollisionAPI(s.GetPrimAtPath(paths[2])).GetApproximationAttr().Get(),'none')
        result=ensure_bed_collisions(s)
        self.assertEqual((result['added'],result['enabled'],result['existing']),(0,0,3))
        for path in paths:self.assertFalse(s.GetPrimAtPath(path).HasAPI(UsdPhysics.RigidBodyAPI))

    def test_missing_background_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError,'대상이 없습니다'):ensure_bed_collisions(Usd.Stage.CreateInMemory())

if __name__=='__main__':unittest.main()
