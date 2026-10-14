"""선택적 Route Server 연결이 기존 그래프/pose 실행을 바꾸지 않는지 검사."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S, ModuleType
from unittest.mock import patch


class TestNavigatorDispatch(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).parents[2]/'farm_navigation/farm_navigation'
        modules={}
        def fake(name,**values):
            m=ModuleType(name);m.__dict__.update(values);modules[name]=m
        fake('rclpy');fake('rclpy.node',Node=object)
        fake('nav_test',__path__=[str(root)])
        fake('nav_test.navigation_types',NavigationSettings=object,NavigationStatus=lambda *a:S(phase=a[1] if len(a)>1 else 'IDLE'),NavigationResult=object,RoutePlan=object)
        for mod,cls in [('nav2_client','Nav2Client'),('pose_provider','PoseProvider'),('motion_monitor','MotionMonitor')]:fake('nav_test.'+mod,**{cls:object})
        fake('nav_test.path_builder',build_path=lambda *a:None)
        fake('nav_test.arrival',measure_arrival=lambda *a:{},arrival_description=str)
        spec=importlib.util.spec_from_file_location('nav_test.navigator',root/'navigator.py')
        m=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules):spec.loader.exec_module(m)
        self.Nav=m.Navigator
        class Matrix:
            def __getitem__(self,key):return 1. if key==(0,3) else 2.
        self.poses=S(current=lambda check:Matrix())
        self.settings=S(mode='follow_path',max_start_distance_m=.1,max_goal_distance_m=.02,
                        tf_recovery_enabled=False)
    def nav(self,graph=None,planner=None,client=None):
        return self.Nav(S(),self.settings,client or S(),self.poses,S(),lambda:None,graph,route_planner=planner)
    def test_existing_graph_unchanged(self):
        calls=[]
        n=self.nav(graph=S(plan=lambda *a:calls.append(a) or 'legacy'))
        assert n.plan((3.,4.))=='legacy'
        assert calls==[((1.,2.),(3.,4.),.1,.02)]
    def test_route_server_is_selected(self):
        calls=[]
        n=self.nav(planner=S(plan=lambda *a:calls.append(a) or 'server'))
        assert n.plan((3.,4.))=='server'
        assert calls[0][:2]==((1.,2.),(3.,4.))
    def test_pose_does_not_call_graph(self):
        self.settings.mode='navigate_to_pose'
        n=self.nav(graph=S(plan=lambda *a:self.fail('graph called')))
        assert n.plan((3.,4.)) is None
    def test_cancel_covers_planner_and_controller(self):
        calls=[]
        n=self.nav(planner=S(cancel=lambda:calls.append('route')),client=S(cancel=lambda:calls.append('controller')))
        n.cancel_nav()
        assert calls==['route','controller']


if __name__=='__main__':unittest.main()
