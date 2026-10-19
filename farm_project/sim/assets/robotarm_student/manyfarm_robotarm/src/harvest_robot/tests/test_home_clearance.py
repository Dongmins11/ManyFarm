import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harvest_runtime.home_clearance import screened_home_path

class HomeTests(unittest.TestCase):
    def test_direct_path_does_not_replay_old_target(self):
        kin=SimpleNamespace(fk=lambda q,l:np.array([[1,0,0,.4],[0,1,0,0],[0,0,1,.9],[0,0,0,1]]),
                            grasp_fk=lambda q,d:np.array([[1,0,0,.4],[0,1,0,0],[0,0,1,.9],[0,0,0,1]]))
        cfg=SimpleNamespace(box_min=(.305,-.095,.506),box_max=(.495,.095,.701),diameter=.07,length=.075)
        start=np.array([.5,.3,.1,0,0,1.1]);home=np.array([0,0,0,0,0,1.1])
        path=screened_home_path(start,home,kin,[],cfg)
        np.testing.assert_allclose(path[0],start);np.testing.assert_allclose(path[-1],home)
        self.assertTrue((np.diff(path[:,:3],axis=0)<=0).all())
        with self.assertRaises(RuntimeError):screened_home_path(start,home,kin,[[.4,0,.9]],cfg)
