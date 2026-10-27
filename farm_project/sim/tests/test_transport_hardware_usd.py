"""USD Python 전용: 접촉 레이어가 원본 구동/관성/외경을 보존하는지 검사."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
try:
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
except ImportError:
    Usd=None
ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'sim/assets/robots/transport_robot/urdf/transport_robot.portable'


@unittest.skipIf(Usd is None,'Isaac USD Python 환경 필요')
class TransportAssetTests(unittest.TestCase):
    def setUp(self):
        self.source=Usd.Stage.Open(str(ASSET/'transport_robot.portable.usd'))
        self.runtime=Usd.Stage.Open(str(ASSET/'transport_robot.sim.usda'))
        self.path=str(self.source.GetDefaultPrim().GetPath())

    def test_drive_and_inertia_unchanged(self):
        count=0
        for p in self.source.Traverse():
            for a in p.GetAttributes():
                if a.GetName().startswith(('drive:', 'physics:mass','physics:diagonalInertia','physics:centerOfMass')):
                    self.assertEqual(a.Get(),self.runtime.GetPrimAtPath(p.GetPath()).GetAttribute(a.GetName()).Get())
                    count+=1
        self.assertGreater(count,30)

    def test_camera_visible_geometry_has_no_nested_instances(self):
        self.assertFalse([p for p in self.runtime.Traverse()
                          if p.IsInstance() and '/visuals' in str(p.GetPath())])

    def test_tire_outer_radius_width_and_original_disabled_only_in_overlay(self):
        for name in ('wheel_left_link','wheel_right_link'):
            wheel=self.runtime.GetPrimAtPath(self.path+'/'+name)
            tires=[UsdGeom.Cylinder(p) for p in Usd.PrimRange(wheel) if p.GetName().startswith('TireCollision')]
            self.assertEqual(len(tires),21)
            self.assertAlmostEqual(max(t.GetRadiusAttr().Get() for t in tires),.033,places=7)
            edges=[]
            for t in tires:
                z=UsdGeom.Xformable(t).GetLocalTransformation().ExtractTranslation()[2]
                half=t.GetHeightAttr().Get()/2;edges.extend([z-half,z+half])
                self.assertTrue(UsdPhysics.CollisionAPI(t.GetPrim()).GetCollisionEnabledAttr().Get())
            self.assertAlmostEqual(max(edges)-min(edges),.018,places=7)
            path=self.path+'/'+name+'/collisions/mesh_0/cylinder'
            self.assertFalse(UsdPhysics.CollisionAPI(self.runtime.GetPrimAtPath(path)).GetCollisionEnabledAttr().Get())
            self.assertTrue(UsdPhysics.CollisionAPI(self.source.GetPrimAtPath(path)).GetCollisionEnabledAttr().Get())

    def test_contact_materials_are_local_to_intended_links(self):
        for link,expected in [('caster_back_left_link',0.),('caster_back_right_link',0.),
                              ('wheel_left_link',.8),('wheel_right_link',.8)]:
            for p in Usd.PrimRange(self.runtime.GetPrimAtPath(self.path+'/'+link)):
                if p.HasAPI(UsdPhysics.CollisionAPI) and UsdPhysics.CollisionAPI(p).GetCollisionEnabledAttr().Get():
                    material,_=UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial(materialPurpose='physics')
                    self.assertAlmostEqual(UsdPhysics.MaterialAPI(material.GetPrim()).GetDynamicFrictionAttr().Get(),expected,places=6)
        p=self.runtime.GetPrimAtPath(self.path+'/SimPhysicsMaterials/PassiveCaster')
        self.assertEqual(p.GetAttribute('physxMaterial:frictionCombineMode').Get(),'min')

    def test_camera_mount_matches_optical_extrinsics(self):
        sys.path[:0]=[str(ROOT/p) for p in ('sim/ros_ws/src/farm_sim_runtime','sim/ros_ws/src/farm_sim_devices')]
        from farm_sim_runtime.apriltag_scene import mount_camera
        cfg=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())
        self.runtime.SetEditTarget(self.runtime.GetSessionLayer())
        mount_camera(self.runtime,self.path,cfg)
        cache=UsdGeom.XformCache()
        def matrix(path):return np.asarray(cache.GetLocalToWorldTransform(self.runtime.GetPrimAtPath(path))).T
        actual=np.linalg.inv(matrix(self.path+'/base_footprint'))@matrix(self.path+'/base_link/docking_camera')@np.diag([1.,-1.,-1.,1.])
        np.testing.assert_allclose(actual,cfg['camera']['T_base_optical'],atol=1e-10)


if __name__=='__main__':unittest.main()
