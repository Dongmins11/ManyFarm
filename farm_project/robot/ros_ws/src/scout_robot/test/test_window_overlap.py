import unittest
from dataclasses import replace
from scout_robot.b_planner import Config,Fruit,plan_harvest,extend_plan
from scout_robot.window_overlap import reduce_overlap

class WindowOverlapTests(unittest.TestCase):
    def setUp(self):
        self.c=Config(route_start=-1,route_end=3,bed_y=.5,membership_margin=0)
    def fruit(self,id,x):return Fruit(id,x,.5,.5)
    def task(self,id,x):return plan_harvest([self.fruit(id,x)],self.c).tasks[0]
    def overlap(self,a,b):return max(0,min(a.window_x_max,b.window_x_max)-max(a.window_x_min,b.window_x_min))
    def test_severe_overlap_reduced_and_members_retained(self):
        old=self.task('old',1);f=self.fruit('new',.9);new=self.task('new',.9)
        t=reduce_overlap(new,[old],{'new':f},self.c,.5)
        self.assertLess(self.overlap(t,old),self.overlap(new,old))
        self.assertEqual(new.member_ids,t.member_ids)
        self.assertGreaterEqual(f.x,t.safe_x_min)
        self.assertLessEqual(f.x,t.safe_x_max)
        self.assertAlmostEqual(t.window_x_max-t.window_x_min,.35)
        self.assertAlmostEqual(t.base_x-new.base_x,t.window_x_min-new.window_x_min)
    def test_existing_windows_never_move(self):
        old=plan_harvest([self.fruit('old',1)],self.c)
        new=extend_plan(old,[self.fruit('old',1),self.fruit('new',.9)],self.c,overlap_trigger_ratio=.5)
        self.assertEqual(old.tasks[0],new.tasks[0])
    def test_disabled_is_identical(self):
        old=plan_harvest([self.fruit('old',1)],self.c);obs=[self.fruit('old',1),self.fruit('new',.9)]
        self.assertEqual(extend_plan(old,obs,self.c),extend_plan(old,obs,self.c,overlap_trigger_ratio=None))
    def test_route_bounds(self):
        c=replace(self.c,route_start=.8,route_end=1.5)
        old=self.task('old',1);new=self.task('new',.9)
        t=reduce_overlap(new,[old],{'new':self.fruit('new',.9)},c,.5)
        self.assertGreaterEqual(t.base_x,c.route_start-1e-9)
        self.assertLessEqual(t.base_x,c.route_end+1e-9)
    def test_no_overlap_unchanged(self):
        new=self.task('new',2)
        self.assertEqual(new,reduce_overlap(new,[self.task('old',1)],{'new':self.fruit('new',2)},self.c,.5))
    def test_reverse_direction(self):
        c=replace(self.c,direction=-1)
        f=self.fruit('new',1.1);old=plan_harvest([self.fruit('old',1)],c).tasks[0];new=plan_harvest([f],c).tasks[0]
        t=reduce_overlap(new,[old],{'new':f},c,.5)
        self.assertLess(self.overlap(t,old),self.overlap(new,old))
        self.assertGreaterEqual(f.x,t.safe_x_min);self.assertLessEqual(f.x,t.safe_x_max)
