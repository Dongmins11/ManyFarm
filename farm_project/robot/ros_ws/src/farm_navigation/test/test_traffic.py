"""실제 생성 ROS 타입 + 가짜 전송으로 등록·허가·취소 경합과 공간 보존을 검증한다."""
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest

from rclpy.task import Future
from farm_interfaces.msg import TrafficContext, TrafficControlState, TrafficRegistration, RobotStatus
from farm_interfaces.action import AcquirePassage
from farm_interfaces.srv import GetPassageState, ReleasePassage
from builtin_interfaces.msg import Time
from farm_navigation.traffic_client import TrafficClient
from farm_navigation.traffic_contract import TrafficIds, TrafficRegistry
from farm_navigation.route import RouteGraph
from farm_navigation.navigation_types import NavigationSettings, RoutePlan
from farm_navigation.path_builder import build_path
from farm_navigation.nav2_client import Nav2Client

ROOT = Path(__file__).resolve().parents[5]
REGISTRY = ROOT/'sim/ros_ws/src/farm_sim_config/config/traffic/traffic_zones.yaml'


class Transport:
    def __init__(self, *args, **kwargs):
        self.requests = []
        self.goals = []
        self.available = True
    def service_is_ready(self): return self.available
    def server_is_ready(self): return self.available
    def call_async(self, req):
        future = Future(); self.requests.append((deepcopy(req),future)); return future
    def send_goal_async(self, goal, feedback_callback=None):
        future = Future(); self.goals.append((deepcopy(goal),future,feedback_callback)); return future
    def remove_pending_request(self,future): pass
    def destroy(self): pass


class Node:
    def __init__(self):
        self.now = 10_000_000_000
        self.publishers = {}
        self.errors = []
    def get_clock(self): return NS(now=lambda:NS(nanoseconds=self.now,to_msg=lambda:Time()))
    def create_publisher(self, cls, topic, qos):
        messages = self.publishers.setdefault(topic,[])
        return NS(publish=lambda msg:messages.append(deepcopy(msg)))
    def create_subscription(self,*args,**kwargs): return None
    def create_client(self,*args,**kwargs): return Transport()
    def create_timer(self,*args,**kwargs): return None
    def destroy_timer(self,*args): pass
    def get_logger(self): return NS(error=self.errors.append, warning=self.errors.append)


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.node = Node()
        self.settings = NavigationSettings(mode='follow_path')
        self.profile = {'robot_id':'scout_01','map_id':'farm_map_v1',
            'route_graph':str(ROOT/'sim/ros_ws/src/farm_sim_config/maps/graph.geojson'),
            'traffic':{'registry':str(REGISTRY),'state_file':str(Path(self.tmp.name)/'ids.db')}}
        with patch('farm_navigation.traffic_client.ActionClient',Transport):
            self.client = TrafficClient(self.node,ROOT,self.profile,self.settings,lambda:'task_01')
        self.addCleanup(self.client.close)

    def control(self, phase='WAIT_POSITION', state='WAIT_POSITION', sync='sync_01', epoch='epoch_01', sequence=1):
        return TrafficControlState(server_epoch=epoch,state_sequence=sequence,phase=phase,
            zone_revision=self.client.registry.data['zone_revision'],robots=[TrafficRegistration(robot_id='scout_01',boot_id=self.client.boot_id,
            sync_id=sync,registration_state=state,accepted_status_sequence=2 if state=='REGISTERED' else 0)])

    def discover(self, control=None):
        self.client._discover()
        req,future=self.client.get_client.requests[-1]
        control = control or self.control()
        future.set_result(GetPassageState.Response(query_id=req.query_id,error_code='NONE',
            current_server_epoch=control.server_epoch,control_state=control))

    def status(self, sequence=2, stamp=None, xy=None):
        c=self.client
        p = xy or c.registry.graph.nodes[10100]
        msg=RobotStatus(robot_id='scout_01',boot_id=c.boot_id,sequence=sequence,error_code='NONE')
        msg.pose.position.x,msg.pose.position.y=map(float,p)
        c.on_status(msg,self.node.now if stamp is None else stamp)

    def ready(self):
        self.discover()
        self.node.now += 1_000_000_000
        self.status()
        self.client._control(self.control('READY','REGISTERED',sequence=2))
        self.assertTrue(self.client.ready)

    def path(self):
        g=self.client.registry.graph
        e=g.edges[0]
        points=(g.nodes[e.start],g.nodes[e.end])
        return build_path(RoutePlan('p',g.revision,'map',points,(e.edge_id,),1.),0.,Time())

    def run_acquire(self):
        result=[]
        previous=len(self.client.acquire_client.goals)
        def run():
            try: result.append(self.client.acquire(self.path(),lambda:None))
            except Exception as error: result.append(error)
        thread=threading.Thread(target=run,daemon=True);thread.start()
        end=time.monotonic()+3
        while len(self.client.acquire_client.goals)==previous and time.monotonic()<end:time.sleep(.01)
        self.assertGreater(len(self.client.acquire_client.goals),previous)
        return thread,result

    def accept(self):
        goal,future,feedback=self.client.acquire_client.goals[-1]
        result=Future();cancels=[]
        handle=NS(accepted=True,get_result_async=lambda:result,cancel_goal_async=lambda:cancels.append(1))
        future.set_result(handle)
        return goal,result,cancels,feedback

    def grant(self,goal,result_future,**changes):
        ctx=deepcopy(goal.context);ctx.permit_id='permit_001'
        result=AcquirePassage.Result(context=ctx,result_code='GRANTED',permission_state='ACTIVE',
            granted_node_ids=goal.route_node_ids,granted_edge_ids=goal.route_edge_ids,
            allocated_zone_ids=['sim:N:'+goal.route_node_ids[-1]],stop_node_id=goal.stop_node_id,error_code='NONE')
        for k,v in changes.items():setattr(result,k,v)
        result_future.set_result(NS(status=4,result=result))

    def test_registration_requires_sample_after_sync_and_not_just_new_sequence(self):
        self.discover()
        self.status(1,self.node.now)
        self.assertEqual(self.client.position_status,0)
        self.node.now+=1_000_000_000;self.status(2)
        self.assertEqual(self.client.position_status,2)
        self.assertFalse(self.client.ready)
        self.client._control(self.control('READY','REGISTERED',sequence=2))
        self.assertTrue(self.client.ready)

    def test_goal_acceptance_and_empty_feedback_do_not_allow_movement(self):
        self.ready();thread,result=self.run_acquire();goal,future,_,feedback=self.accept()
        feedback(NS(feedback=AcquirePassage.Feedback(context=goal.context,feedback_sequence=1,request_state='WAITING')))
        time.sleep(.05)
        self.assertTrue(thread.is_alive());self.assertFalse(self.client.moving)
        self.grant(goal,future);thread.join(2)
        self.assertFalse(thread.is_alive());self.assertIsInstance(result[0],tuple)
        self.assertTrue(self.client.moving)

    def test_partial_grant_does_not_start(self):
        self.ready();thread,result=self.run_acquire();goal,future,_,_=self.accept()
        self.grant(goal,future,granted_edge_ids=[]);thread.join(2)
        self.assertIsInstance(result[0],RuntimeError);self.assertFalse(self.client.moving)

    def test_feedback_replaces_and_old_sequence_is_ignored(self):
        self.ready();thread,result=self.run_acquire();goal,future,_,_=self.accept()
        request=self.client.pending
        request['changed']=False
        # acquire가 우회 계산을 실행하지 않도록 테스트 중에는 lock을 유지한다.
        with self.client.lock:
            for seq,nodes in [(2,['9002']),(1,['9001']),(3,[])]:
                self.client._feedback(request,AcquirePassage.Feedback(context=goal.context,feedback_sequence=seq,request_state="WAITING",blocked_node_ids=nodes))
            self.assertEqual(request['blocked'],((),()))
        self.grant(goal,future);thread.join(2)

    def test_clock_backward_needs_new_epoch(self):
        self.ready();self.node.now=1;self.client._tick()
        req,future=self.client.get_client.requests[-1]
        future.set_result(GetPassageState.Response(query_id=req.query_id,error_code='NONE',current_server_epoch='epoch_01',control_state=self.control('READY','REGISTERED',sequence=3)))
        self.assertFalse(self.client.ready)
        self.assertEqual(self.client.reset_epoch,'epoch_01')

    def test_new_epoch_during_wait_blocks_late_grant(self):
        self.ready();thread,result=self.run_acquire();goal,future,cancels,_=self.accept()
        self.client._control(self.control(epoch='epoch_02'))
        self.grant(goal,future);thread.join(2)
        self.assertIsInstance(result[0],RuntimeError);self.assertFalse(self.client.moving)
        self.assertTrue(cancels)

    def test_current_permission_is_kept_until_new_result(self):
        self.ready();thread,result=self.run_acquire();goal,future,_,_=self.accept()
        self.grant(goal,future);thread.join(2)
        old=self.client.current
        self.client.movement_finished()
        thread,result=self.run_acquire()
        # 기다리는 동안 이전 context를 Progress에 사용한다.
        self.assertIs(self.client.current,old)
        goal,future,_,_=self.accept();self.grant(goal,future);thread.join(2)

    def test_nav2_is_not_called_without_permission(self):
        trace=[]
        nav=object.__new__(Nav2Client)
        traffic=NS(motion_clients=[],acquire=lambda *args:(_ for _ in ()).throw(RuntimeError('wait')))
        nav._node=NS(_traffic=traffic)
        nav._execute_authorized=lambda *args:trace.append('move')
        with self.assertRaises(RuntimeError):nav.execute((0,0),0,self.path(),lambda:None)
        self.assertEqual(trace,[])

    def test_invalidation_during_execution_is_checked(self):
        self.ready();thread,result=self.run_acquire();goal,future,_,_=self.accept()
        self.grant(goal,future);thread.join(2)
        generation=result[0][1]
        self.client.check(generation)
        self.client._control(self.control('WAIT_STOP','WAIT_STOP','sync_02',sequence=3))
        with self.assertRaises(RuntimeError):self.client.check(generation)
        self.assertTrue(self.client.stopped)

    def test_abandoned_grant_is_queried_and_never_executed(self):
        self.ready();thread,result=self.run_acquire();goal,future,cancels,_=self.accept()
        request=self.client.pending
        # 취소 요청이 발급 직전에 도착한 상황을 만든다.
        request['abandoned']=True
        self.client._invalidate('operator cancel')
        thread.join(2)
        self.grant(goal,future)
        self.assertFalse(self.client.moving)
        query,response=self.client.get_client.requests[-1]
        self.assertEqual(query.request_id,goal.context.request_id)
        self.assertEqual(query.permit_id,'permit_001')
        ctx=deepcopy(goal.context);ctx.permit_id='permit_001'
        response.set_result(GetPassageState.Response(query_id=query.query_id,found=True,error_code='NONE',
            context=ctx,current_server_epoch='epoch_01',permission_state='ACTIVE'))
        self.assertIsNone(self.client.pending)

    def test_release_uses_exact_progress_and_refusal_preserves_resources(self):
        self.ready()
        c=self.client
        ctx=TrafficContext(robot_id=c.robot_id,boot_id=c.boot_id,request_id='req_001',permit_id='permit_001',server_epoch=c.epoch)
        zone='sim:N:9002'
        permit=dict(context=ctx,zones={zone},seen={zone},sequence=0,hold=set(),abandoned=False)
        c.current=permit;c.permits=[permit];c.occupied=set();c.moving=False
        c._release_exited()
        req,future=c.release_client.requests[-1]
        self.assertEqual(req.release_mode,'EXITED')
        self.assertEqual(req.progress_sequence,self.node.publishers['traffic_progress'][-1].sequence)
        future.set_result(ReleasePassage.Response(context=ctx,operation_sequence=1,current_server_epoch=c.epoch,
            released=False,error_code='EXIT_NOT_CONFIRMED',remaining_zone_ids=[zone]))
        self.assertEqual(permit['zones'],{zone})
        c._release_exited()
        self.assertEqual(len(c.release_client.requests),1)
        c.latest_stamp+=1
        c._release_exited()
        req,future=c.release_client.requests[-1]
        self.assertEqual(req.operation_sequence,2)
        future.set_result(ReleasePassage.Response(context=ctx,operation_sequence=2,current_server_epoch=c.epoch,
            released=True,error_code='NONE',released_zone_ids=[zone],permit_closed=True))
        self.assertEqual(c.permits,[])

    def test_work_reservation_not_released_while_body_is_in_work_group(self):
        self.ready();c=self.client
        a,b='sim:N:9002','sim:N:9001'
        permit=dict(context=TrafficContext(server_epoch=c.epoch),zones={a,b},seen={a,b},sequence=0,
            hold={a,b},abandoned=False)
        c.permits=[permit];c.current=permit;c.occupied={a};c.moving=False
        c._release_exited()
        self.assertEqual(c.release_client.requests,[])

    def test_future_reentry_zone_is_not_released_mid_motion(self):
        self.ready();c=self.client;zone='sim:N:9002'
        permit=dict(context=TrafficContext(server_epoch=c.epoch),zones={zone},seen={zone},sequence=0,
            hold=set(),abandoned=False,future={zone:10},cursor=5)
        c.permits=[permit];c.current=permit;c.occupied=set();c.moving=True
        c._release_exited()
        self.assertEqual(c.release_client.requests,[])

    def test_new_epoch_discards_unanswered_query_and_ignores_old_response(self):
        c=self.client;c._discover()
        old_request,old_future=c.get_client.requests[-1]
        c._control(self.control(epoch='epoch_02'))
        c._discover();new_request,new_future=c.get_client.requests[-1]
        old_future.set_result(GetPassageState.Response(query_id=old_request.query_id,error_code='NONE',
            current_server_epoch='epoch_01',control_state=self.control()))
        self.assertIs(c.query,new_future)
        new_future.set_result(GetPassageState.Response(query_id=new_request.query_id,error_code='NONE',
            current_server_epoch='epoch_02',control_state=self.control(epoch='epoch_02')))
        self.assertEqual(c.epoch,'epoch_02')

    def test_id_counters_survive_restart_and_lock_duplicate_process(self):
        path=Path(self.tmp.name)/'other.db'
        ids=TrafficIds(path,'r');self.assertEqual(ids.next('boot'),'boot_01')
        with self.assertRaises(RuntimeError):TrafficIds(path,'r')
        ids.close();ids=TrafficIds(path,'r')
        self.assertEqual(ids.next('boot'),'boot_02');ids.close()

    def test_graph_blocking_cannot_snap_to_other_lane(self):
        graph=self.client.registry.graph
        edge=graph.edges[0]
        a,b=graph.nodes[edge.start],graph.nodes[edge.end]
        midpoint=((a[0]+b[0])/2,(a[1]+b[1])/2)
        with self.assertRaises(ValueError):
            graph.plan(midpoint,b,blocked_edges=frozenset(e.edge_id for e in graph.edges))

    def test_registry_rejects_unregistered_path_and_preserves_shared_offsets(self):
        with self.assertRaises(ValueError):self.client.registry.route([(100.,100.),(101.,100.)],.1)
        graph=RouteGraph(ROOT/'sim/ros_ws/src/farm_sim_config/maps/harvest_graph.geojson')
        other=TrafficRegistry(REGISTRY,graph,'harvest_01')
        offsets=[n for n in graph.nodes if n in self.client.registry.graph.nodes and graph.nodes[n]!=self.client.registry.graph.nodes[n]]
        self.assertEqual(len(offsets),24)
        self.assertEqual(other.data['zone_revision'],self.client.registry.data['zone_revision'])

    def test_short_pose_connector_keeps_graph_route(self):
        registry=self.client.registry;g=registry.graph;e=g.edges[0]
        a,b=g.nodes[e.start],g.nodes[e.end]
        dx,dy=b[0]-a[0],b[1]-a[1];length=(dx*dx+dy*dy)**.5
        start=(a[0]-dy/length*.02,a[1]+dx/length*.02)
        expected=registry.route([a,b],.1)
        self.assertEqual(registry.route([start,a,b],.1),expected)

    def test_finished_task_preserves_actual_occupied_resources(self):
        self.ready()
        zone = next(iter(self.client.occupied))
        context = TrafficContext(robot_id=self.client.robot_id, boot_id=self.client.boot_id,
            request_id='req_done', permit_id='permit_done', server_epoch=self.client.epoch)
        permit = dict(context=context, task_id='test_drive', zones={zone}, seen={zone},
                      hold=set(), abandoned=False, sequence=0)
        self.client.permits.append(permit)
        self.client.current = permit
        self.client.finish_task('test_drive', .1)
        self.assertEqual(permit['zones'], {zone})
        self.assertIs(self.client.current, permit)
        self.assertEqual(self.client._context().permit_id, 'permit_done')
        self.assertTrue(permit['abandoned'])
        self.assertFalse(self.client.release_client.requests)

    def test_finish_task_does_not_claim_unresolved_wait_canceled(self):
        self.ready()
        thread, result = self.run_acquire()
        goal, future, cancels, _ = self.accept()
        # 관제에서 취소 종료를 돌려주지 않으면 CANCELED 완료로 꾸미지 않는다.
        with self.assertRaisesRegex(RuntimeError, '종료 미확인'):
            self.client.finish_task('task_01', .05)
        self.assertTrue(cancels)
        ctx = deepcopy(goal.context)
        future.set_result(NS(status=5, result=AcquirePassage.Result(context=ctx,
            result_code='CANCELED', permission_state='NONE', error_code='NONE')))
        thread.join(1)
        self.assertFalse(thread.is_alive())

    def test_boundary_contact_is_occupied(self):
        r=self.client.registry;z=next(iter(r.zones));bounds=r.zones[z]['bounds_m']
        hx=r.profile['length_m']/2+r.profile['margin_each_side_m']
        x=bounds[2]+hx;y=(bounds[1]+bounds[3])/2
        self.assertIn(z,r.occupied(x,y,0.))
        self.assertNotIn(z,r.occupied(x+.001,y,0.))


if __name__=='__main__':unittest.main()
