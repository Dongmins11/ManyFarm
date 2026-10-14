"""실제 OpenUSD 합성 검사. Isaac/PhysX·실제 농장 자산 검증과 구분합니다."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics, Gf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sim/ros_ws/src/farm_sim_runtime'))
from farm_sim_runtime.scout_mount import install_scout_mount, scout_mount_static_tf


class ScoutMountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/scout.json').read_text())
        self.stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(self.stage, 1.)
        UsdGeom.SetStageUpAxis(self.stage, 'Z')
        self.path = self.cfg['scene_binding']['robot_prim']
        root = UsdGeom.Xform.Define(self.stage, self.path)
        root.AddTranslateOp().Set((3., -7., 0.))
        root.AddRotateZOp().Set(37.)
        UsdGeom.Xform.Define(self.stage, self.path+'/base_footprint')
        base = UsdGeom.Xform.Define(self.stage, self.path+'/base_link')
        base.AddTranslateOp().Set((0., 0., .01))
        UsdPhysics.RigidBodyAPI.Apply(base.GetPrim())
        UsdPhysics.MassAPI.Apply(base.GetPrim()).CreateMassAttr(1.23)
        cam = UsdGeom.Camera.Define(self.stage, self.path+'/base_link/scout_camera')
        cam.AddTranslateOp().Set((0., 0., .59))
        cam.CreateFocalLengthAttr(17.)
        cam.CreateHorizontalApertureAttr(20.)
        cam.CreateClippingRangeAttr((.12, 12.))
        self.source = self.stage.GetRootLayer().ExportToString()
        self.stage.SetEditTarget(self.stage.GetSessionLayer())

    def transform(self, relative: str) -> np.ndarray:
        cache = UsdGeom.XformCache()
        b=self.stage.GetPrimAtPath(self.path+'/base_footprint')
        p=self.stage.GetPrimAtPath(self.path+'/'+relative)
        return (np.linalg.inv(np.asarray(cache.GetLocalToWorldTransform(b)).T)
                @ np.asarray(cache.GetLocalToWorldTransform(p)).T)

    def test_mount_camera_frames_and_physics_preserved(self) -> None:
        install_scout_mount(self.stage, ROOT, self.path, self.cfg)
        a=np.deg2rad(1.)
        optical=self.transform('base_link/scout_camera') @ np.diag([1.,-1.,-1.,1.])
        np.testing.assert_allclose(optical[:3,3],[-.049,.055,.595],atol=1e-9)
        np.testing.assert_allclose(optical[:3,2],[0.,np.cos(a),-np.sin(a)],atol=1e-9)
        np.testing.assert_allclose(self.transform('base_link/scout_mount/picam_optical_frame')[:3,3],[-.032,.063,.117],atol=1e-9)
        self.assertAlmostEqual(self.transform('base_link/scout_mount/scout_mast_top')[2,3],.62)
        cam=UsdGeom.Camera(self.stage.GetPrimAtPath(self.path+'/base_link/scout_camera'))
        self.assertEqual(cam.GetFocalLengthAttr().Get(),17.)
        self.assertEqual(cam.GetHorizontalApertureAttr().Get(),20.)
        np.testing.assert_allclose(cam.GetClippingRangeAttr().Get(),[.12,12.])
        base=self.stage.GetPrimAtPath(self.path+'/base_link')
        self.assertAlmostEqual(UsdPhysics.MassAPI(base).GetMassAttr().Get(),1.23,places=6)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(),self.source)
        tfs=scout_mount_static_tf(self.stage,self.path,self.cfg)
        self.assertEqual(len(tfs),4)
        self.assertEqual(len({x['child'] for x in tfs}),4)
        for tf in tfs:self.assertEqual(tf['parent'],self.cfg['frames']['base_link'])
        d435=next(x for x in tfs if x['child'].endswith('/camera_color_optical_frame'))
        np.testing.assert_allclose(d435['translation'],[-.049,.055,.585],atol=1e-9)

    def test_idempotence_and_robot_motion(self) -> None:
        install_scout_mount(self.stage, ROOT, self.path, self.cfg)
        before=self.stage.GetSessionLayer().ExportToString()
        install_scout_mount(self.stage, ROOT, self.path, self.cfg)
        self.assertEqual(self.stage.GetSessionLayer().ExportToString(),before)
        base=UsdGeom.Xformable(self.stage.GetPrimAtPath(self.path+'/base_link'))
        base.GetOrderedXformOps()[0].Set((.2,.3,.01))
        np.testing.assert_allclose(self.transform('base_link/scout_mount/picam_frame')[:3,3],[.168,.363,.117],atol=1e-9)

    def test_disabled_configuration_noop(self) -> None:
        cfg=dict(self.cfg);cfg.pop('scout_mount_asset');cfg.pop('tag_camera',None)
        before=self.stage.GetSessionLayer().ExportToString()
        install_scout_mount(self.stage,ROOT,self.path,cfg)
        self.assertEqual(scout_mount_static_tf(self.stage,self.path,cfg),[])
        self.assertEqual(before,self.stage.GetSessionLayer().ExportToString())

    def test_missing_camera_fails_without_silent_new_sensor(self) -> None:
        self.stage.GetPrimAtPath(self.path+'/base_link/scout_camera').SetActive(False)
        with self.assertRaises(ValueError):
            install_scout_mount(self.stage,ROOT,self.path,self.cfg)

    def test_picam_renders_at_mount_and_reuses_its_optical_tf(self) -> None:
        install_scout_mount(self.stage,ROOT,self.path,self.cfg)
        relative=self.cfg['scene_binding']['tag_camera_relative']
        camera=self.stage.GetPrimAtPath(self.path+'/'+relative)
        self.assertTrue(camera.IsA(UsdGeom.Camera))
        actual=self.transform(relative)@np.diag([1.,-1.,-1.,1.])
        np.testing.assert_allclose(actual,self.cfg['tag_camera']['T_base_optical'],atol=1e-9)
        np.testing.assert_allclose(actual,self.transform('base_link/scout_mount/picam_optical_frame'),atol=1e-9)
        transforms=scout_mount_static_tf(self.stage,self.path,self.cfg)
        selected=[tf for tf in transforms if tf['child']==self.cfg['frames']['tag_camera_optical']]
        self.assertEqual(len(selected),1)
        # base_link 물리 변환을 따라가며, 원본 USD에 새 센서를 저장하지 않습니다.
        base=UsdGeom.Xformable(self.stage.GetPrimAtPath(self.path+'/base_link'))
        base.GetOrderedXformOps()[0].Set((.2,.3,.01))
        np.testing.assert_allclose(self.transform(relative)[:3,3],actual[:3,3]+[.2,.3,0.],atol=1e-9)
        self.assertEqual(self.stage.GetRootLayer().ExportToString(),self.source)

    def test_tag_camera_requires_mount(self) -> None:
        cfg=dict(self.cfg);cfg.pop('scout_mount_asset')
        with self.assertRaisesRegex(ValueError,'scout_mount_asset'):
            install_scout_mount(self.stage,ROOT,self.path,cfg)

    def test_tag_camera_cannot_replace_survey_camera(self) -> None:
        self.cfg['scene_binding']['tag_camera_relative']=self.cfg['scene_binding']['camera_relative']
        with self.assertRaisesRegex(ValueError,'PiCam'):
            install_scout_mount(self.stage,ROOT,self.path,self.cfg)

if __name__=='__main__':
    unittest.main()
