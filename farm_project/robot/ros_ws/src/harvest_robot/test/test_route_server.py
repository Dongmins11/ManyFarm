"""ComputeRoute 어댑터의 계약 시험. ROS/DDS 통합 시험을 대체하지 않는다."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
from concurrent.futures import Future
sys.path.insert(0,str(Path(__file__).parents[1]))


def pose(x=0., y=0., frame='map'):
    return S(header=S(frame_id=frame,stamp=None),pose=S(position=S(x=x,y=y,z=0.),orientation=S(w=1.)))


def done(value):
    f=Future();f.set_result(value);return f


class FakeClient:
    def __init__(self,*args,**kwargs):
        self.accepted=True
        self.status=4
        self.error=0
        self.canceled=False
        self.path=S(header=S(frame_id='map'),poses=[pose(0,0),pose(1,0)])
    def server_is_ready(self):return True
    def send_goal_async(self,request):
        self.request=request
        return done(S(accepted=self.accepted,get_result_async=lambda:done(S(status=self.status,
            result=S(path=self.path,error_code=self.error,error_msg='test error'))),
            cancel_goal_async=lambda:done(None)))
    def destroy(self):pass


class TestRouteServer(unittest.TestCase):
    def setUp(self):
        import dataclasses
        @dataclasses.dataclass
        class Plan:
            plan_id:str
            graph_revision:str
            frame_id:str
            points:tuple
            edge_ids:tuple
            distance_m:float
        fake={
            'rclpy':S(), 'rclpy.action':S(ActionClient=FakeClient),
            'nav2_msgs':S(), 'nav2_msgs.action':S(ComputeRoute=S(Goal=lambda:S(start=pose(),goal=pose()))),
            'action_msgs':S(), 'action_msgs.msg':S(GoalStatus=S(STATUS_SUCCEEDED=4,STATUS_ABORTED=6,STATUS_CANCELED=5)),
            'farm_navigation':S(), 'farm_navigation.navigation_types':S(RoutePlan=Plan)}
        path=Path(__file__).parents[1]/'harvest_robot/route_server.py'
        spec=importlib.util.spec_from_file_location('route_under_test',path)
        self.module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,fake):spec.loader.exec_module(self.module)
        self.settings=S(map_frame='map',readiness_timeout_s=.01,response_timeout_s=.01,cancel_timeout_s=.01,
            max_start_distance_m=.1,max_goal_distance_m=.02)
        self.node=S(get_clock=lambda:S(now=lambda:S(to_msg=lambda:123)))
        self.planner=self.module.RouteServerPlanner(self.node,self.settings,None,'graph-hash')
    def test_exact_request_and_success(self):
        result=self.planner.plan((0,0),(1,0),lambda:None)
        req=self.planner.client.request
        assert req.use_start and req.use_poses
        assert req.goal.pose.position.x==1
        assert req.goal.header.frame_id=='map'
        assert result.points==((0,0),(1,0))
        assert self.planner.pending is None
    def test_rejected_goal(self):
        self.planner.client.accepted=False
        with self.assertRaisesRegex(RuntimeError,'거절'):self.planner.plan((0,0),(1,0),lambda:None)
        assert self.planner.pending is None
    def test_error_result_never_falls_back(self):
        self.planner.client.error=405
        with self.assertRaisesRegex(RuntimeError,'실패'):self.planner.plan((0,0),(1,0),lambda:None)
    def test_wrong_frame(self):
        self.planner.client.path.header.frame_id='other_map'
        with self.assertRaises(ValueError):self.planner.plan((0,0),(1,0),lambda:None)
    def test_empty_path(self):
        self.planner.client.path.poses=[]
        with self.assertRaises(ValueError):self.planner.plan((0,0),(1,0),lambda:None)
    def test_gap_not_silently_connected(self):
        with self.assertRaises(ValueError):self.planner.plan((5,0),(1,0),lambda:None)
    def test_nonfinite_path(self):
        self.planner.client.path.poses[1].pose.position.x=float('nan')
        with self.assertRaises(ValueError):self.planner.plan((0,0),(1,0),lambda:None)
    def test_path_shape_preserved(self):
        self.planner.client.path.poses=[pose(0,0),pose(.2,.3),pose(.7,.2),pose(1,0)]
        result=self.planner.plan((0,0),(1,0),lambda:None)
        assert result.points==((0,0),(.2,.3),(.7,.2),(1,0))
    def test_late_acceptance_is_retained_for_cancel(self):
        pending=Future()
        self.planner.client.send_goal_async=lambda req:pending
        with self.assertRaises(TimeoutError):self.planner.plan((0,0),(1,0),lambda:None)
        assert self.planner.pending is pending
        canceled=[]
        result=Future()
        def cancel():
            canceled.append(True);result.set_result(S(status=5));return done(None)
        pending.set_result(S(accepted=True,get_result_async=lambda:result,cancel_goal_async=cancel))
        self.planner.cancel()
        assert canceled and self.planner.pending is None


if __name__=='__main__':unittest.main()
