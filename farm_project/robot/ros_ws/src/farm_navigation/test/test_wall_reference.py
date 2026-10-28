"""벽 분석의 기하·불량 입력 검증. 물리 주행 시험을 대체하지 않는다."""
import unittest
import numpy as np
from farm_navigation.wall_reference import fit_wall, footprint_gap, scan_points, summarize

class TestWallReference(unittest.TestCase):
    def points(self, angle=0.):
        normal=np.array([np.cos(angle),np.sin(angle)])
        tangent=np.array([-normal[1],normal[0]])
        return .6*normal+np.linspace(-.4,.4,100)[:,None]*tangent
    def test_distance(self):
        self.assertAlmostEqual(fit_wall(self.points())['distance_m'],.6)
    def test_angle(self):
        self.assertAlmostEqual(fit_wall(self.points(.2))['normal_angle_rad'],.2)
    def test_outliers(self):
        p=np.vstack([self.points(),[[2.,2.],[1.,-1.],[2.,-1.]]])
        self.assertAlmostEqual(fit_wall(p)['distance_m'],.6)
    def test_gap(self):
        self.assertAlmostEqual(footprint_gap(fit_wall(self.points()),[[.3,-.25],[.3,.25],[-.3,.25],[-.3,-.25]]),.3)
    def test_insufficient(self):
        with self.assertRaises(ValueError): fit_wall(self.points()[:5])
    def test_degenerate(self):
        with self.assertRaises(ValueError): fit_wall(np.ones((100,2)))
    def test_corner_rejected(self):
        with self.assertRaises(ValueError): fit_wall(np.vstack([self.points(),self.points(np.pi/2)]))
    def test_invalid(self):
        p=self.points();p[0,0]=np.nan
        with self.assertRaises(ValueError): fit_wall(p)
    def record(self):
        angles=np.linspace(-.5,.5,100)
        return {'stamp_ns':1,'base_from_scan':np.eye(4).tolist(),'scan':{
            'angle_min':float(angles[0]),'angle_increment':float(angles[1]-angles[0]),
            'range_min':.05,'range_max':10.,'ranges':(.6/np.cos(angles)).tolist()}}
    def test_scan_geometry(self):
        self.assertAlmostEqual(fit_wall(scan_points(self.record(),(-35,35)))['distance_m'],.6)
    def test_sensor_offset(self):
        r=self.record();r['base_from_scan'][0][3]=.1
        self.assertAlmostEqual(fit_wall(scan_points(r,(-35,35)))['distance_m'],.7)
    def test_invalid_ranges(self):
        r=self.record();r['scan']['ranges'][:3]=[None,100.,0.]
        self.assertEqual(len(scan_points(r,(-35,35))),97)
    def test_duplicate_stamps(self):
        report=summarize([self.record(),self.record()],(-35,35))
        self.assertEqual(report['accepted_frames'],1)
        self.assertEqual(len(report['rejected_frames']),1)
        self.assertFalse(report['approved_for_motion'])
    def test_bad_sector(self):
        with self.assertRaises(ValueError): scan_points(self.record(),(35,-35))
    def test_no_wall(self):
        with self.assertRaises(ValueError): summarize([],(-35,35))

if __name__=='__main__': unittest.main()
