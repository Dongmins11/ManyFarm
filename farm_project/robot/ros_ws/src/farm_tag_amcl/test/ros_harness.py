"""하드웨어 없이 실제 ROS/AMCL 라이브러리의 시각 정합과 필터 갱신을 검사한다."""
import os,sys,time,math,json,subprocess,signal
from pathlib import Path
import rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy,ReliabilityPolicy
from lifecycle_msgs.srv import ChangeState
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped,TransformStamped
from tf2_msgs.msg import TFMessage
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String,Bool
if os.environ.get('ROS_DOMAIN_ID') not in ('219','220') or os.environ.get('ROS_AUTOMATIC_DISCOVERY_RANGE')!='LOCALHOST':
 raise RuntimeError('하드웨어 없는 검사는 별도 Domain219/220 및 LOCALHOST에서만 실행합니다.')
OUTPUT=Path(os.environ.get('TAG_AMCL_TEST_OUTPUT','/tmp/tag_amcl_test'))
OUTPUT.mkdir(parents=True,exist_ok=True)
from builtin_interfaces.msg import Time

def stamp(v: float) -> Time:
 n=round(v*1e9);return Time(sec=n//10**9,nanosec=n%10**9)
class Harness:
 def __init__(self,exe: str,case: str,map_data: dict | None=None,params_path: str | None=None) -> None:
  self.log=OUTPUT/(case+'.log');self.out=self.log.open('w')
  self.proc=subprocess.Popen([exe,'--ros-args','-r','__ns:=/probe','--params-file',str(params_path or OUTPUT/'params.yaml')],stdout=self.out,stderr=subprocess.STDOUT)
  rclpy.init();self.n=rclpy.create_node('test_driver');self.events=[];self.poses=[]
  self.n.create_subscription(String,'/probe/tag_localization/events',lambda m:self.events.append(json.loads(m.data)),100)
  self.n.create_subscription(PoseWithCovarianceStamped,'/probe/amcl_pose',lambda m:self.poses.append(m),100)
  transient=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,reliability=ReliabilityPolicy.RELIABLE)
  self.pmap=self.n.create_publisher(OccupancyGrid,'/map',transient)
  self.pstatic=self.n.create_publisher(TFMessage,'/tf_static',transient)
  self.ptf=self.n.create_publisher(TFMessage,'/tf',100)
  self.pclock=self.n.create_publisher(Clock,'/clock',10)
  self.pscan=self.n.create_publisher(LaserScan,'/scan',10)
  self.pinitial=self.n.create_publisher(PoseWithCovarianceStamped,'/probe/initialpose',10)
  self.pcorrection=self.n.create_publisher(String,'/probe/tag_localization/correction',10)
  self.pcontrol=self.n.create_publisher(String,'/probe/tag_localization/control',10)
  self.token='task0';self.control_seq=0;self.request_seq=0;self.begin_ns=100000000000
  self.penable=self.n.create_publisher(Bool,'/probe/probe_enabled',10)
  self.client=self.n.create_client(ChangeState,'/probe/amcl/change_state')
  assert self.client.wait_for_service(timeout_sec=8),'AMCL service missing: '+self.log.read_text()[-1500:]
  self.clock(100)
  self.transition(1)
  g=OccupancyGrid();g.header.frame_id='map';g.info.resolution=.1;g.info.width=100;g.info.height=100;g.info.origin.position.x=-5.;g.info.origin.position.y=-5.;g.info.origin.orientation.w=1.
  g.data=[100 if x in [0,99] or y in [0,99] else 0 for y in range(100) for x in range(100)]
  if map_data:
   g.info.width=map_data['width'];g.info.height=map_data['height'];g.info.resolution=map_data['resolution'];g.info.origin.position.x=float(map_data['origin'][0]);g.info.origin.position.y=float(map_data['origin'][1]);g.data=map_data['data']
  self.map_message=g;self.pmap.publish(g)
  tr=TransformStamped();tr.header.frame_id='base_footprint';tr.child_frame_id='laser';tr.transform.rotation.w=1.;self.pstatic.publish(TFMessage(transforms=[tr]));self.spin(.2)
  self.transition(3);self.penable.publish(Bool(data=True));self.spin(.08)
  self.tf(99.9,0.);self.tf(100.,0.);self.pinitial.publish(self.pose(100.,0.));self.spin(.06)
  self.scan(100.);self.spin(.15);self.control(True)
 def spin(self,d: float=.04) -> None:
  end=time.monotonic()+d
  while time.monotonic()<end:
   if hasattr(self,'now') and time.monotonic()-getattr(self,'_clock_sent',0)>.02:
    self.pclock.publish(Clock(clock=Time(sec=self.now_ns//10**9,nanosec=self.now_ns%10**9)));self._clock_sent=time.monotonic()
   rclpy.spin_once(self.n,timeout_sec=min(.01,max(0,end-time.monotonic())))
 def transition(self,i: int) -> None:
  q=ChangeState.Request();q.transition.id=i;f=self.client.call_async(q);rclpy.spin_until_future_complete(self.n,f,timeout_sec=5);assert f.done() and f.result().success,(i,self.log.read_text()[-1000:])
 def clock(self,t: float) -> None:self.now=t;self.now_ns=round(t*1e9);self.pclock.publish(Clock(clock=stamp(t)));self.spin()
 def tf(self,t: float,x: float,y: float=0.,yaw: float=0.) -> None:
  tr=TransformStamped();tr.header.stamp=stamp(t);tr.header.frame_id='odom';tr.child_frame_id='base_footprint';tr.transform.translation.x=float(x);tr.transform.translation.y=float(y);tr.transform.rotation.z=math.sin(yaw/2);tr.transform.rotation.w=math.cos(yaw/2);self.ptf.publish(TFMessage(transforms=[tr]));self.spin(.025)
 def pose(self,t: float,x: float,y: float=0.,yaw: float=0.) -> PoseWithCovarianceStamped:
  m=PoseWithCovarianceStamped();m.header.stamp=stamp(t);m.header.frame_id='map';m.pose.pose.position.x=float(x);m.pose.pose.position.y=float(y);m.pose.pose.orientation.z=math.sin(yaw/2);m.pose.pose.orientation.w=math.cos(yaw/2);return m
 def control(self,enabled: bool=True,**extra: object) -> None:
  self.control_seq+=1
  payload=dict(robot_id='probe',map_id='test_map',token=self.token,sequence=self.control_seq,
               begin_ns=self.begin_ns,stamp_ns=self.now_ns,enabled=enabled)
  payload.update(extra);self.pcontrol.publish(String(data=json.dumps(payload)));self.spin(.03)
 def new_task(self) -> None:
  self.token+='n';self.begin_ns=self.now_ns;self.control(True)
 def request(self,t: float,x: float=1.,y: float=0.,yaw: float=0.,**extra: object) -> None:
  self.request_seq+=1
  payload=dict(protocol=1,robot_id='probe',map_id='test_map',token=self.token,producer_session='producer',
    sequence=self.request_seq,source_stamp_ns=round(t*1e9),pose_stamp_ns=round(t*1e9),sent_stamp_ns=round(self.now*1e9),
    frame_id='map',pose=[x,y,yaw],covariance=[0.]*36)
  payload.update(extra);self.pcorrection.publish(String(data=json.dumps(payload)));self.spin(.03)
 def kinds(self,kind: str) -> list:return [e for e in self.events if e['kind']==kind]
 def scan(self,t: float) -> None:
  m=LaserScan();m.header.stamp=stamp(t);m.header.frame_id='laser';m.angle_min=-math.pi;m.angle_max=math.pi;m.angle_increment=2*math.pi/35;m.range_min=.05;m.range_max=10.;m.ranges=[float('inf')]*36;self.pscan.publish(m);self.spin(.04)
 def applied(self) -> list:return self.kinds('tag_correction_applied')
 def close(self) -> None:
  self.proc.send_signal(signal.SIGINT)
  try:self.proc.wait(timeout=5)
  except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
  self.out.close();self.n.destroy_node();rclpy.shutdown()

params='''/probe/amcl:
  ros__parameters:
    use_sim_time: true
    tag_robot_id: probe
    tag_map_id: test_map
    base_frame_id: base_footprint
    odom_frame_id: odom
    global_frame_id: map
    scan_topic: /scan
    map_topic: /map
    transform_tolerance: 1.0
    min_particles: 100
    max_particles: 100
    max_beams: 30
    alpha1: 0.0
    alpha2: 0.0
    alpha3: 0.0
    alpha4: 0.0
    alpha5: 0.0
    update_min_d: 0.0
    update_min_a: 0.0
    resample_interval: 1
'''
(OUTPUT/'params.yaml').write_text(params)
