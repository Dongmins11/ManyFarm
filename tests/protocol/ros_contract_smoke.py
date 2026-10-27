"""격리 localhost 도메인에서 실제 Communication/Controller와 대역 장치만 실행한다."""
import sys,tempfile,time,threading
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup,MutuallyExclusiveCallbackGroup
from farm_interfaces.action import NavigateToNode,BucketUnload,ReturnToStation,TransportPickup
from farm_interfaces.srv import UnloadEvent,TransferEvent
from transport_robot.transport_communication import TransportCommunication
from transport_robot.transport_mission import TransportMission
from transport_robot.transport_state_controller import TransportStateController
from transport_robot.mission_types import utc
from test_protocol_flow import Nav,Dock,Device

class Fixture(Node):
 def __init__(self,journal):
  super().__init__('protocol_fixture',namespace='/contract_test_transport')
  self.callbacks=ReentrantCallbackGroup();self.stopping=False;self.calls=[]
  self.declare_parameter('allow_route_checks',True)
  dest=dict(configured=True,approach_node_id=17,approach_yaw_rad=0.,clearance_node_id=17,clearance_yaw_rad=0.,docking_profile='sort_01')
  self.profile=dict(robot_id='contract_test_transport',map_id='farm_map_v1',registry={'destinations':{'SORT_01':dest}},precision_enabled=True,precision_registry={'profiles':{'sort_01':dict(configured=True,clearance_corridor_verified=True)}},pickup_profile='sort_01')
  self.graph=NS(nodes={17:(0.,0.)},_candidates=lambda *a:[])
  self.settings=NS(map_frame='map',max_goal_distance_m=.02)
  self._pose=np.eye(4)
  self.mission=TransportMission(journal);self.docking=Dock(self.calls);self.device=Device(self.calls)
  self.controller=TransportStateController(Nav(self.calls),self.mission,self.docking,self.device)
  self.communication=TransportCommunication(self)
  self.create_timer(.01,self.communication.update,callback_group=MutuallyExclusiveCallbackGroup())
 def route_ready(self):return True

def until(f):
 end=time.monotonic()+8
 while not f() and time.monotonic()<end:time.sleep(.01)
 assert f(),'timeout'
def wait(f):until(f.done);return f.result()
def common(g,task):
 g.robot_id='contract_test_transport';g.task_id=task;g.map_id='farm_map_v1';g.timestamp=utc();return g

def run():
 rclpy.init()
 with tempfile.TemporaryDirectory() as d:
  n=Fixture(Path(d)/'tasks.json');client=Node('protocol_client',namespace='/contract_test_transport')
  ex=MultiThreadedExecutor(num_threads=6);ex.add_node(n);ex.add_node(client);th=threading.Thread(target=ex.spin);th.start()
  actions={name:ActionClient(client,typ,name) for typ,name in [(BucketUnload,'bucket_unload'),(ReturnToStation,'return_to_station')]}
  event=client.create_client(UnloadEvent,'unload_event')
  def unload_event(task='U1',station='SORT_01'):
   return wait(event.call_async(UnloadEvent.Request(robot_id='contract_test_transport',task_id=task,station_id=station,event='UNLOAD_READY',timestamp=utc())))
  try:
   for c in actions.values():assert c.wait_for_server(timeout_sec=5)
   assert event.wait_for_service(timeout_sec=5)
   removed=ActionClient(client,NavigateToNode,'navigate_to_node')
   assert not removed.wait_for_server(timeout_sec=1), 'removed server still exposed'
   removed.destroy()
   events=[]
   g=common(BucketUnload.Goal(),'U1');g.station_id='SORT_01'
   h=wait(actions['bucket_unload'].send_goal_async(g,feedback_callback=lambda m:events.append(m.feedback.event)));assert h.accepted
   until(lambda:'WAITING_FOR_UNLOAD' in events)
   assert not unload_event(station='wrong').accepted
   busy=common(BucketUnload.Goal(),'busy');busy.station_id='SORT_01'
   assert not wait(actions['bucket_unload'].send_goal_async(busy)).accepted
   assert unload_event().accepted
   r=wait(h.get_result_async());assert r.status==4 and r.result.result_code=='SUCCESS'
   assert n.calls==['move','dock','UNLOAD'],n.calls
   assert n.controller.docked_request.task_id=='U1'
   assert not unload_event().accepted
   g=common(ReturnToStation.Goal(),'R1');g.station_id='SORT_01'
   h=wait(actions['return_to_station'].send_goal_async(g));assert h.accepted
   r=wait(h.get_result_async());assert r.status==4 and r.result.docked
   assert n.calls[-3:]==['clear:U1','move','dock'],n.calls
   # 다음 하역의 준비 대기 중 실제 Action cancel -> CANCELED, 하역 없음.
   g=common(BucketUnload.Goal(),'U2');g.station_id='SORT_01'
   h=wait(actions['bucket_unload'].send_goal_async(g));assert h.accepted
   until(lambda:n.controller.unload.phase=='WAIT_READY')
   assert wait(h.cancel_goal_async()).goals_canceling
   r=wait(h.get_result_async());assert r.status==5 and r.result.result_code=='CANCELED',r
   assert n.calls.count('UNLOAD')==1
   # 시험 모드: 외부 준비 서비스/기구 없이 도킹하고 성공 보고 없이 유지한다.
   from transport_robot.device_port import UnavailableDevice
   n.device=UnavailableDevice();n.controller.device=n.device
   n.profile['sorter_dock_trial']={'enabled':True,'station_id':'SORT_01'}
   n.profile['precision_registry']['profiles']['sort_01']['clearance_corridor_verified']=False
   g=common(BucketUnload.Goal(),'TRIAL1');g.station_id='SORT_01'
   h=wait(actions['bucket_unload'].send_goal_async(g));assert h.accepted
   until(lambda:n.controller.docked_request is not None and n.controller.docked_request.task_id=='TRIAL1')
   assert n.controller.busy and n.calls.count('UNLOAD')==1
   assert wait(h.cancel_goal_async()).goals_canceling
   r=wait(h.get_result_async());assert r.status==5 and r.result.result_code=='CANCELED'
   assert n.controller.blocked
   print('PASS ROS: navigate_to_node server absent, busy rejection, unload service identity, hold after unload, next-job departure, Action cancellation.')
  finally:
   n.stopping=True;n.controller.cancel();until(lambda:not n.communication.busy)
   ex.shutdown();th.join();n.controller.close();n.communication.close();client.destroy_node();n.destroy_node();rclpy.shutdown()
if __name__=='__main__':run()
