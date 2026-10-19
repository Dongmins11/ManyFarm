import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from harvest_rl.rgbd_geometry import intrinsics,valid_depth,align_depth_to_color,project

class RGBDGeometryTests(unittest.TestCase):
    def test_identity_alignment_and_holes(self):
        k=intrinsics(4,3,69)
        d=np.array([[0,1,1,0],[2,2,2,2],[0,0,0,0]],dtype=np.float32)
        np.testing.assert_allclose(align_depth_to_color(d,k,k,np.eye(4),(3,4)),d)

    def test_extrinsic_translation_and_zbuffer(self):
        k=np.array([[1.,0,0],[0,1.,0],[0,0,1.]])
        # pixel0 at Z1 -> u1, pixel1 at Z2 -> u1.5 -> u2
        t=np.eye(4);t[0,3]=1
        aligned=align_depth_to_color(np.array([[1.,2.]]),k,k,t,(1,3))
        np.testing.assert_allclose(aligned,[[0,1,2]])
        # Two input pixels hit same pixel when target focal length is smaller.
        kc=k.copy();kc[0,0]=.1
        aligned=align_depth_to_color(np.array([[2.,1.]]),k,kc,np.eye(4),(1,2))
        np.testing.assert_allclose(aligned,[[1,0]])

    def test_depth_invalid_range_and_z_projection(self):
        d,valid=valid_depth(np.array([[np.inf,np.nan,.1,.5,4.]]),.28,3.)
        np.testing.assert_array_equal(valid,[[False,False,False,True,False]])
        np.testing.assert_allclose(d,[[0,0,0,.5,0]])
        k=intrinsics(640,360,69)
        uv,z,inside=project([[0,0,1],[0,0,-1]],np.eye(4),k,(360,640))
        np.testing.assert_allclose(uv[0],[320,180])
        np.testing.assert_array_equal(inside,[True,False])

    def test_nominal_depth_wider_than_rgb(self):
        kc=intrinsics(640,360,69);kd=intrinsics(848,480,87)
        point=[[.8,0,1]]
        self.assertFalse(project(point,np.eye(4),kc,(360,640))[2][0])
        self.assertTrue(project(point,np.eye(4),kd,(480,848))[2][0])
