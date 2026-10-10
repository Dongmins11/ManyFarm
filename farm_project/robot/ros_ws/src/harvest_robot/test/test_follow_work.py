"""실제 수확 초기화와 공통 계획→Path→Action 연결 검사. ROS I/O만 대역이다."""
from pathlib import Path
import ast
import copy
from dataclasses import replace
import importlib.util
import json
import math
import sys
import threading
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[5]
SRC=ROOT/'robot/ros_ws/src'
for package in ('harvest_robot','farm_navigation'):
    sys.path.insert(0,str(SRC/package))
from farm_navigation.configuration import load_environment, read_mapping, resolve_file
from farm_navigation.navigation_types import NavigationSettings
from farm_navigation.route import RouteGraph
from harvest_robot.staged_navigation import StagedNavigation, load_sections
from harvest_robot.contract import validate_task
from harvest_robot.mission import HarvestMission, MissionCanceled


def message() -> NS:
    return NS(header=NS(frame_id='',stamp=None),pose=NS(position=NS(x=0.,y=0.,z=0.),orientation=NS(x=0.,y=0.,z=0.,w=1.)))


class Future:
    def __init__(self, result: object, done: bool=True) -> None:self.value=result;self.ready=done
    def done(self) -> bool:return self.ready
    def result(self) -> object:return self.value


class PathMessage:
    def __init__(self) -> None:self.header=NS(frame_id="",stamp=None);self.poses=[]


class Follow:
    class Goal:
        pass


class Pose:
    class Goal:
        def __init__(self) -> None:self.pose=message()


class Client:
    def __init__(self, node: object, action: object, name: str, **kwargs: object) -> None:
        self.node=node;self.action=action;self.name=name
    def server_is_ready(self) -> bool:return True
    def send_goal_async(self, goal: object) -> Future:
        self.node.sent.append((self.name,goal))
        failure=self.node.fail_work and len(self.node.sent)>1
        self.result=Future(NS(status=6 if failure else 4,result=NS(error_code=1 if failure else 0)))
        if self.node.cancel_work and len(self.node.sent)>1:
            self.result.ready=False;self.node.stopping=True
        if not failure:
            pose=goal.path.poses[-1] if self.action is Follow else goal.pose
            self.node.position=(pose.pose.position.x,pose.pose.position.y,
                                2*math.atan2(pose.pose.orientation.z,pose.pose.orientation.w))
        return Future(NS(accepted=True,get_result_async=lambda:self.result,cancel_goal_async=self.cancel))
    def cancel(self) -> Future:
        self.node.canceled.append(self.name);self.result.value.status=5;self.result.ready=True
        return Future(NS())
    def destroy(self) -> None:pass


class Parameters:
    controllers = ('RPP', 'HarvestApproach', 'HarvestWork')
    def service_is_ready(self) -> bool:return True
    def call_async(self, request: object) -> Future:
        base={'goal_checker_plugins':['general_goal_checker'],'controller_plugins':list(self.controllers),
              'progress_checker_plugins':['progress_checker']}
        checker={'plugin':'nav2_controller::SimpleGoalChecker','xy_goal_tolerance':.04,
                 'yaw_goal_tolerance':.043633,'stateful':True,'symmetric_yaw_tolerance':False}
        base.update({'general_goal_checker.'+k:v for k,v in checker.items()})
        return Future(NS(values=[base[name] for name in request.names]))
    def remove_pending_request(self, future: object) -> None:pass


class Node:
    def __init__(self, name: str) -> None:
        self.parameters={'project_root':str(ROOT),'environment_config':'robot/config/environments/harvest_real.yaml','mode':'real'}
        self.sent=[];self.canceled=[];self.position=(1.188,-.02,-math.pi/2)
        self.fail_work=False;self.cancel_work=False;self.tag_events=[]
    def declare_parameter(self, name: str, value: object) -> None:self.parameters.setdefault(name,value)
    def get_parameter(self, name: str) -> NS:return NS(value=self.parameters[name])
    def create_publisher(self, *args: object) -> NS:return NS(publish=lambda value:None)
    def create_client(self, *args: object, **kwargs: object) -> Parameters:return Parameters()
    def get_logger(self) -> NS:return NS(info=lambda value:None)
    def get_clock(self) -> NS:return NS(now=lambda:NS(to_msg=lambda:NS(sec=0,nanosec=0)))


class Poses:
    def __init__(self, node: Node, settings: object) -> None:self.node=node
    def current(self, check: object) -> np.ndarray:
        check();x,y,a=self.node.position;t=np.eye(4)
        t[0,3]=x;t[1,3]=y;t[:2,:2]=[[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]]
        return t
    def lookup(self, target: str, source: str, stamp: int, check: object) -> np.ndarray:return self.current(check)


class Motion:
    def __init__(self, *args: object) -> None:pass
    def wait_stopped(self, check: object) -> int:check();return 123


class RoutePlanner:
    """Route Server 통신만 대역. 작업 경로는 실제 RouteGraph로 계산한다."""
    def __init__(self, node: Node, *args: object) -> None:
        self.node=node;self.calls=[];self.canceled=False
        self.graph=RouteGraph(ROOT/'robot/config/maps/many_farm/graph.geojson')
    def plan(self, start: tuple, goal: tuple, check: object) -> object:
        check();self.calls.append((start,goal));return self.graph.plan(start,goal,.1,.02)
    def cancel(self) -> None:self.canceled=True


def construct(mode: str='route_then_follow', approach: str='graph',
              config_overrides: dict | None = None) -> Node:
    """운영 HarvestNode 클래스 본문을 실행한다. 설정/알고리즘은 실제 코드를 사용한다."""
    modules={}
    def stub(name: str, **values: object) -> None:
        module=ModuleType(name);module.__dict__.update(values);modules[name]=module
    stub('rclpy');stub('rclpy.node',Node=Node);stub('rclpy.callback_groups',CallbackGroup=object)
    stub('rclpy.task',Future=Future);stub('rclpy.action',ActionClient=Client)
    stub('rclpy.action.client',ClientGoalHandle=object)
    stub('rclpy.parameter',parameter_value_to_python=lambda v:v)
    stub('rcl_interfaces.srv',GetParameters=NS(Request=lambda:NS(names=[])))
    stub('nav2_msgs.action',NavigateToPose=Pose,FollowPath=Follow)
    stub('action_msgs.msg',GoalStatus=NS(STATUS_SUCCEEDED=4,STATUS_CANCELED=5,STATUS_ABORTED=6))
    stub('nav_msgs.msg',Path=PathMessage)
    stub('geometry_msgs.msg',PoseStamped=message);stub('builtin_interfaces.msg',Time=object)
    stub('follow_verify',__path__=[str(SRC/'farm_navigation/farm_navigation')])
    stub('follow_verify.pose_provider',PoseProvider=Poses)
    stub('follow_verify.motion_monitor',MotionMonitor=Motion)
    stub('harvest_robot.route_server',RouteServerPlanner=RoutePlanner)
    def load(name: str, path: Path) -> object:
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;spec.loader.exec_module(module);return module
    with patch.dict(sys.modules,modules):
        client=load('follow_verify.nav2_client',SRC/'farm_navigation/farm_navigation/nav2_client.py')
        navigator=load('follow_verify.navigator',SRC/'farm_navigation/farm_navigation/navigator.py')
        tree=ast.parse((SRC/'harvest_robot/harvest_robot/node.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HarvestNode')
        def mapping(path: Path) -> dict:
            data=read_mapping(path)
            if 'movement_mode' in data:
                data=copy.deepcopy(data);data['movement_mode']=mode;data['approach_planner']=approach
                for key, value in (config_overrides or {}).items():
                    if value is None:data.pop(key, None)
                    else:data[key]=value
            return data
        env=dict(__name__='harvest_robot._follow_verify',__package__='harvest_robot',
            Node=Node,Path=Path,load_environment=load_environment,resolve_file=resolve_file,read_mapping=mapping,
            NavigationSettings=NavigationSettings,RouteGraph=RouteGraph,Navigator=navigator.Navigator,
            Nav2Client=client.Nav2Client,PoseProvider=Poses,MotionMonitor=Motion,replace=replace,
            ReentrantCallbackGroup=lambda:None,threading=threading,StagedNavigation=StagedNavigation,
            load_sections=load_sections,String=object,QoSProfile=lambda **kw:kw,
            ReliabilityPolicy=NS(RELIABLE=1),DurabilityPolicy=NS(TRANSIENT_LOCAL=1),
            HarvestCommunication=lambda node:NS(),rclpy=NS(ok=lambda:True),MissionCanceled=MissionCanceled,
            json=json)
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'<operational HarvestNode>','exec'),env)
        return env['HarvestNode']()


def request(xy: tuple=(1.188,-4.02), section: str='SEC_01') -> NS:
    return NS(robot_id='harvest_01',map_id=read_mapping(ROOT/'robot/config/harvest/harvest_real.json')['map_id'],section_id=section,
        harvest_task=NS(task_id='test',window_id='opaque',expected_count=0,
            goal_pose=NS(frame_id='map',position=NS(x=xy[0],y=xy[1],z=0.),yaw=-math.pi/2)))


class FollowWork(unittest.TestCase):
    def test_real_configuration_selects_follow(self) -> None:
        cfg=read_mapping(ROOT/'robot/config/harvest/harvest_real.json')
        self.assertEqual(cfg['movement_mode'],'route_then_follow')
        self.assertNotIn('route_corridor',cfg)

    def test_operational_node_sends_graph_paths_in_both_stages(self) -> None:
        n=construct();goal=request();validate_task(goal,n.config)
        result=HarvestMission(n,goal).run()
        self.assertEqual([name for name,_ in n.sent],['follow_path','follow_path'])
        self.assertIsNone(n.route_planner)
        path=n.sent[-1][1].path
        self.assertGreater(len(path.poses),2)
        self.assertTrue(all(abs(p.pose.position.x-1.188)<1e-9 for p in path.poses))
        self.assertAlmostEqual(path.poses[-1].pose.position.y,goal.harvest_task.goal_pose.position.y)
        self.assertAlmostEqual(2*math.atan2(path.poses[-1].pose.orientation.z,path.poses[-1].pose.orientation.w),-math.pi/2)
        self.assertEqual(n.sent[-1][1].controller_id,'HarvestWork')
        self.assertEqual([r['phase'] for r in n.navigation_log if 'phase' in r],['SECTION_APPROACH','WINDOW_MOVE'])
        self.assertEqual(result['stamp_ns'],123)
        self.assertTrue(n.navigation_log[-1]['route']['edge_ids'])

    def test_mid_edge_goal_is_exact_and_same_section_skips_entry(self) -> None:
        n=construct();HarvestMission(n,request((1.188,-2.3))).run()
        HarvestMission(n,request((1.188,-2.7))).run()
        self.assertIsNone(n.route_planner)
        self.assertEqual(len(n.sent),3)
        self.assertAlmostEqual(n.sent[-1][1].path.poses[-1].pose.position.y,-2.7)

    def test_exit_uses_follow_and_keeps_transition_order(self) -> None:
        n=construct();HarvestMission(n,request((1.188,-2.3))).run()
        n.staged_navigation.sections['SECOND']=n.staged_navigation.sections['SEC_01']
        n.config['sections']['SECOND']=n.config['sections']['SEC_01']
        before=len(n.sent);HarvestMission(n,request((1.188,-2.7),'SECOND')).run()
        self.assertEqual([name for name,_ in n.sent[before:]],['follow_path']*3)
        phases=[r['phase'] for r in n.navigation_log if 'phase' in r]
        self.assertEqual(phases[-3:],['SECTION_EXIT','SECTION_APPROACH','WINDOW_MOVE'])

    def test_far_goal_rejected_without_pose_fallback(self) -> None:
        n=construct();HarvestMission(n,request((1.188,-2.3))).run();before=len(n.sent)
        with self.assertRaises(ValueError):HarvestMission(n,request((1.398,-2.7))).run()
        self.assertEqual(len(n.sent),before)
        self.assertIsNone(n.staged_navigation.current_section)

    def test_work_failure_does_not_send_pose_goal(self) -> None:
        n=construct();n.fail_work=True
        with self.assertRaises(RuntimeError):HarvestMission(n,request()).run()
        self.assertEqual([name for name,_ in n.sent],['follow_path','follow_path'])
        self.assertIsNone(n.staged_navigation.current_section)

    def test_cancel_and_tag_lifetime_cover_both_stages(self) -> None:
        n=construct();n.cancel_work=True
        n.tag_control=NS(begin=lambda:n.tag_events.append('begin'),end=lambda:n.tag_events.append('end'))
        with self.assertRaises(MissionCanceled):HarvestMission(n,request()).run()
        self.assertEqual(n.tag_events,['begin','end'])
        self.assertEqual(n.canceled,['follow_path'])
        self.assertFalse(n.blocked)

    def test_unknown_section_rejected_by_contract(self) -> None:
        n=construct()
        with self.assertRaises(ValueError):validate_task(request(section='UNKNOWN'),n.config)
        self.assertEqual(n.sent,[])

    def test_start_in_middle_of_zero_ten_reaches_fourteen(self) -> None:
        n=construct();n.position=(.8455,-.02,0.)
        HarvestMission(n,request()).run()
        approach=n.navigation_log[1]['route']
        points=approach['points']
        self.assertAlmostEqual(points[0][0],.8455)
        self.assertTrue(all(p[0] >= .8455-1e-9 for p in points))
        self.assertAlmostEqual(points[-1][1],-1.02)
        self.assertIn('38',approach['edge_ids'])
        self.assertEqual([name for name,_ in n.sent],['follow_path','follow_path'])
        self.assertAlmostEqual(n.sent[-1][1].path.poses[-1].pose.position.y,-4.02)

    def test_mid_harvest_edge_does_not_return_to_ten(self) -> None:
        n=construct();n.position=(1.188,-.096, -math.pi/2)
        HarvestMission(n,request()).run()
        points=n.navigation_log[1]['route']['points']
        self.assertTrue(all(p[1] <= -.096+1e-9 for p in points))

    def test_far_start_fails_before_follow_action(self) -> None:
        n=construct();n.position=(2.0,0.,0.)
        with self.assertRaises(ValueError):HarvestMission(n,request()).run()
        self.assertEqual(n.sent,[])

    def test_old_map_id_rejected(self) -> None:
        n=construct();goal=request();goal.map_id='93f108470604e1afb2d320b8eb128df031e926875a032c03d0b98030c09e067c'
        with self.assertRaises(ValueError):validate_task(goal,n.config)

    def test_explicit_legacy_pose_mode_kept(self) -> None:
        n=construct('route_then_pose', approach='route_server');HarvestMission(n,request()).run()
        self.assertEqual([name for name,_ in n.sent],['follow_path','navigate_to_pose'])

    def test_graph_only_remains_direct_follow(self) -> None:
        n=construct('graph_only');self.assertIsNone(n.staged_navigation)
        HarvestMission(n,request()).run();self.assertEqual([name for name,_ in n.sent],['follow_path'])

if __name__=='__main__':unittest.main()
