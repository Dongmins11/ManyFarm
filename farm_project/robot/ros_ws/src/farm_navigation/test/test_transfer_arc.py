"""원호 기하·오차 판정·설정 보존·셀 면적 충돌 검사를 오프라인 검증한다."""
import copy
import math
import unittest
from farm_navigation.transfer_arc import ArcSpec,arc_path,arc_pose,check_motion,check_complete,add_profile
from farm_navigation.arc_clearance import check_grid

class ArcTests(unittest.TestCase):
    def test_endpoint(self):
        p=arc_path((0,0,0),ArcSpec())[-1]
        for a,b in zip(p,(-.1,-.1,math.pi/2)):self.assertAlmostEqual(a,b)
    def test_rotated_origin(self):
        p=arc_pose((2,3,math.pi/2),.1,math.pi/2)
        self.assertAlmostEqual(p[0],2.1);self.assertAlmostEqual(p[1],2.9)
    def test_spacing(self):
        p=arc_path((0,0,0),ArcSpec())
        self.assertTrue(all(math.dist(a[:2],b[:2])<=.002 for a,b in zip(p,p[1:])))
    def test_reverse_tangent(self):
        p=arc_path((0,0,0),ArcSpec())
        self.assertTrue(all((b[0]-a[0])*math.cos(a[2])+(b[1]-a[1])*math.sin(a[2])<0 for a,b in zip(p,p[1:])))
    def test_invalid(self):
        for value in (0,-1,float('nan'),float('inf'),True):
            with self.subTest(value=value),self.assertRaises(ValueError):ArcSpec(radius=value)
    def test_deviation(self):
        with self.assertRaises(RuntimeError):check_motion((0,0,0),(.02,0,0),ArcSpec())
    def test_wrong_turn(self):
        with self.assertRaises(RuntimeError):check_motion((0,0,0),(0,0,-.2),ArcSpec())
    def test_partial_not_complete(self):
        with self.assertRaises(RuntimeError):check_complete((0,0,0),arc_pose((0,0,0),.1,.4),ArcSpec())
    def test_wrap(self):
        start=(0,0,3.0);check_complete(start,arc_pose(start,.1,math.pi/2),ArcSpec())
    def test_preserves_original(self):
        src={'controller_server':{'ros__parameters':{'controller_plugins':['RPP'],'goal_checker_plugins':['g'],
             'progress_checker_plugins':['p'],'RPP':{'desired_linear_vel':.1}}},'amcl':{'unchanged':True}}
        old=copy.deepcopy(src);out=add_profile(src)
        self.assertEqual(src,old);self.assertEqual(out['amcl'],src['amcl'])
        self.assertEqual(out['controller_server']['ros__parameters']['RPP'],src['controller_server']['ros__parameters']['RPP'])
        self.assertFalse(out['controller_server']['ros__parameters']['TransferArc']['use_rotate_to_heading'])
        self.assertTrue(out['controller_server']['ros__parameters']['TransferArc']['use_collision_detection'])
        with self.assertRaises(ValueError):add_profile(out)

class GridTests(unittest.TestCase):
    def setUp(self):
        self.grid={'metadata':{'resolution':.02,'size_x':100,'size_y':100,'origin':{
            'position':{'x':-1,'y':-1},'orientation':{'x':0,'y':0,'z':0,'w':1}}},'data':[0]*10000}
        self.footprint=[(.32,-.27),(.32,.27),(-.32,.27),(-.32,-.27)]
        self.path=arc_path((0,0,0),ArcSpec())
    def test_empty(self):
        self.assertGreater(check_grid(self.path,self.footprint,(0,0,0),self.grid),0)
    def test_lethal_inside(self):
        self.grid['data'][50*100+50]=254
        with self.assertRaises(RuntimeError):check_grid(self.path,self.footprint,(0,0,0),self.grid)
    def test_unknown_inside(self):
        self.grid['data'][50*100+50]=255
        with self.assertRaises(RuntimeError):check_grid(self.path,self.footprint,(0,0,0),self.grid)
    def test_inflation_not_lethal(self):
        self.grid['data'][50*100+50]=200
        check_grid(self.path,self.footprint,(0,0,0),self.grid)
    def test_out_of_map(self):
        with self.assertRaises(RuntimeError):check_grid(arc_path((2,0,0),ArcSpec()),[(x+2,y) for x,y in self.footprint],(2,0,0),self.grid)
    def test_cell_corner(self):
        # 셀 중심이 밖에 있어도 셀 경계가 footprint와 접하면 거절한다.
        self.grid['data'][50*100+66]=254
        with self.assertRaises(RuntimeError):check_grid(self.path,self.footprint,(0,0,0),self.grid)
    def test_rotated_footprint(self):
        t=.3;c=math.cos(t);s=math.sin(t)
        fp=[(c*x-s*y,s*x+c*y) for x,y in self.footprint]
        check_grid(arc_path((0,0,t),ArcSpec()),fp,(0,0,t),self.grid)
    def test_invalid_footprint(self):
        with self.assertRaises(ValueError):check_grid(self.path,self.footprint[:3],(0,0,0),self.grid)

if __name__=='__main__':unittest.main()
