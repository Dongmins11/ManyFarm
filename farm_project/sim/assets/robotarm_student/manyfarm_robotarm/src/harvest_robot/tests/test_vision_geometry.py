import tempfile,unittest
import numpy as np
from harvest_vision.geometry import Frame,locate
from harvest_vision.pipeline import save_packet,load_packet
class VisionGeometryTest(unittest.TestCase):
    def frame(self):
        return Frame(np.zeros((40,40,3),np.uint8),np.full((40,40),.5,np.float32),
            np.array([[100.,0,19.5],[0,100.,19.5],[0,0,1]]),np.eye(4),1.,1.,'right')
    def test_metric_transform_and_surface_distinction(self):
        f=self.frame();f.arm_from_optical[:3,3]=[1,2,3]
        r=locate(f,np.ones((40,40),bool),1.,centre_offset_m=.035)
        np.testing.assert_allclose(r['surface_arm_m'],[1,2,3.5],atol=1e-6)
        np.testing.assert_allclose(r['grasp_estimate_arm_m'],[1,2,3.535],atol=1e-6)
        self.assertTrue(r['valid']);self.assertFalse(r['control_valid'])
    def test_missing_depth_and_stale_transform(self):
        f=self.frame();mask=np.ones((40,40),bool)
        f.depth_m[:]=np.nan;self.assertFalse(locate(f,mask,1.)['valid'])
        f=self.frame();self.assertFalse(locate(f,mask,2.)['valid'])
        f.pose_stamp_s=.8;self.assertEqual(locate(f,mask,1.)['reason'],'unsynchronised_pose')
    def test_outliers_excluded(self):
        f=self.frame();f.depth_m[10:15]=2.
        r=locate(f,np.ones((40,40),bool),1.)
        self.assertAlmostEqual(r['surface_arm_m'][2],.5)
    def test_bad_frame_rejected(self):
        f=self.frame();f.rectified=False
        with self.assertRaises(ValueError):f.validate()
        f=self.frame();f.arm_from_optical[0,0]=-1
        with self.assertRaises(ValueError):f.validate()
    def test_packet_roundtrip(self):
        f=self.frame()
        with tempfile.TemporaryDirectory() as d:
            save_packet(d,f);g=load_packet(d)
            np.testing.assert_array_equal(f.depth_m,g.depth_m);self.assertEqual(f.frame_id,g.frame_id)

    def test_robot_outside_workspace_not_target(self):
        from harvest_vision.pipeline import process
        class Detector:
            def predict(self,rgb):return [dict(class_id=1,label='Yellow',confidence=.99,bbox=[0,0,39,39],mask=np.ones((40,40),bool))]
        r,_=process(self.frame(),Detector(),1.,arm_roi=([.2,-.2,0],[.4,.2,1]))
        self.assertTrue(r[0]['valid'])
        self.assertFalse(r[0]['candidate_valid'])
        self.assertFalse(r[0]['control_valid'])
