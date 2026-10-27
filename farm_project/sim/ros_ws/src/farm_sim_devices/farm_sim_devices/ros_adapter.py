"""ROS 환경에서만 실행. Isaac 데이터/명령을 동일한 로봇 ROS 토픽으로 연결."""
import json
import math
import time
from collections import deque
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock,ClockType
from rclpy.executors import ExternalShutdownException,MultiThreadedExecutor
from rclpy.qos import qos_profile_sensor_data,QoSProfile,ReliabilityPolicy,DurabilityPolicy
from geometry_msgs.msg import Twist,TwistStamped,TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan,JointState
from rosgraph_msgs.msg import Clock as ClockMessage
from std_msgs.msg import Bool
from tf2_ros import TransformBroadcaster,StaticTransformBroadcaster
from farm_sim_devices.wire import LocalDatagrams


def stamp_message(stamp,ns):
    stamp.sec=int(ns)//1000000000
    stamp.nanosec=int(ns)%1000000000


def finite_vector(value,size):
    return isinstance(value,list) and len(value)==size and all(type(v) in (int,float) and math.isfinite(v) for v in value)


class SimRosAdapter(Node):
    def __init__(self):
        super().__init__('sim_devices')
        self.declare_parameter('config_file','')
        self.declare_parameter('cmd_vel_type','twist')
        path=self.get_parameter('config_file').value
        self.config=json.loads(Path(path).read_text())
        rt=self.config['runtime']
        # 독립 /clock relay가 먼저 전달될 여유. 측정 stamp 자체는 변경하지 않는다.
        delay=rt.get('state_clock_delay_s',0.)
        if type(delay) not in (int,float) or not math.isfinite(delay) or not 0<=delay<=.1:
            raise ValueError('state_clock_delay_s는 0~0.1초이어야 합니다.')
        if delay and (self.config.get('publish_clock',True) or not self.get_parameter('use_sim_time').value):
            raise ValueError('state clock 대기는 독립 clock relay와 use_sim_time이 필요합니다.')
        self.state_clock_delay_ns=round(delay*1e9)
        self.pending_states=deque(maxlen=64)
        self.transport=LocalDatagrams(rt['telemetry_port'],rt['command_port'])
        self.session=None;self.last_packet=-1;self.last_stamp=-1;self.last_seen=-math.inf
        self.cmd_seq=0;self.static_sent=False;self.link_lost=False
        self.odom_pub=self.create_publisher(Odometry,'odom',10)
        self.scan_pub=self.create_publisher(LaserScan,'scan',qos_profile_sensor_data)
        self.joint_pub=self.create_publisher(JointState,'joint_states',10)
        self.clock_pub=self.create_publisher(ClockMessage,'/clock',10) if self.config.get('publish_clock', True) else None
        self.tf=TransformBroadcaster(self);self.static_tf=StaticTransformBroadcaster(self)
        self.camera_ros=None
        self.last_camera_activity=-math.inf
        if self.config['camera'].get('enabled') and self.config['camera'].get('publish_ros'):
            from farm_sim_devices.camera_ros import CameraRos
            self.camera_ros=CameraRos(self,self.config['camera'],self.config['frames']['camera_optical'])
        self.tag_camera_ros=None
        tag_camera=self.config.get('tag_camera',{})
        if tag_camera.get('enabled') and tag_camera.get('publish_ros'):
            from farm_sim_devices.camera_ros import CameraRos
            self.tag_camera_ros=CameraRos(self,tag_camera,self.config['frames']['tag_camera_optical'])
        kind=self.get_parameter('cmd_vel_type').value
        if kind=='twist':
            self.subscription=self.create_subscription(Twist,'cmd_vel',self.command,10)
        elif kind=='twist_stamped':
            self.subscription=self.create_subscription(TwistStamped,'cmd_vel',lambda msg:self.command(msg.twist),10)
        else:raise ValueError('cmd_vel_type은 twist 또는 twist_stamped이어야 합니다.')
        activity=rt.get('harvest_activity',{})
        if not isinstance(activity,dict):raise ValueError('harvest_activity는 설정 객체여야 합니다.')
        self.harvest_activity_enabled=activity.get('enabled',False) is True
        self.harvest_activity_subscription=None
        if self.harvest_activity_enabled:
            topic=activity.get('topic','sim/harvest_activity')
            if not isinstance(topic,str) or not topic.strip():
                raise ValueError('수확 활동 topic은 비어 있지 않은 문자열이어야 합니다.')
            self.harvest_activity_subscription=self.create_subscription(Bool,topic,self.harvest_activity,
                QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.VOLATILE))
        arm=rt.get('harvest_arm',{})
        if not isinstance(arm,dict):raise ValueError('harvest_arm은 설정 객체여야 합니다.')
        self.arm_server=None
        if arm.get('enabled',False) is True:
            from farm_sim_devices.arm_ros import ArmRosServer
            self.arm_server=ArmRosServer(self,arm)
        self.mechanical_server=None
        if rt.get('mechanical_device',{}).get('enabled') is True:
            from farm_sim_devices.mechanical_ros import MechanicalRosServer
            self.mechanical_server=MechanicalRosServer(self)
        self.timer=self.create_timer(.005,self.poll,clock=Clock(clock_type=ClockType.STEADY_TIME))
        self.get_logger().info('Isaac Sim 연결 대기. 속도 명령은 연결 이후에만 전달합니다.')

    def command(self,msg):
        if self.session is None or time.monotonic()-self.last_seen>self.config['runtime']['transport_timeout_s']:
            return
        if not math.isfinite(msg.linear.x) or not math.isfinite(msg.angular.z):return
        self.cmd_seq=time.monotonic_ns()
        self.transport.send(dict(kind='cmd',session=self.session,seq=self.cmd_seq,sent=time.monotonic(),
                                 linear=float(msg.linear.x),angular=float(msg.angular.z)))

    def harvest_activity(self,msg: Bool) -> None:
        """명시적인 Bool 수신 때만 전달합니다. 주행 이벤트 추론·활동 재전송은 없습니다."""
        if not self.harvest_activity_enabled or self.session is None or type(msg.data) is not bool:
            return
        now=time.monotonic()
        if not 0<=now-self.last_seen<=self.config['runtime']['transport_timeout_s']:
            return
        self.transport.send(dict(kind='harvest_activity',session=self.session,seq=time.monotonic_ns(),
            sent=now,robot_id=self.config['robot_id'],active=msg.data))

    def valid(self,m):
        if m.get('kind')!='state' or not isinstance(m.get('session'),str):return False
        if type(m.get('seq')) is not int or type(m.get('stamp_ns')) is not int or m['stamp_ns']<0:return False
        if not finite_vector(m.get('odom'),5):return False
        if not finite_vector(m.get('joint_positions'),2) or not finite_vector(m.get('joint_velocities'),2):return False
        sent=m.get('sent')
        if type(sent) not in (float,int) or not math.isfinite(sent):return False
        if not 0<=time.monotonic()-sent<=self.config['runtime']['transport_timeout_s']:return False
        scan=m.get('scan')
        if scan is not None and (not isinstance(scan,list) or len(scan)!=self.config['lidar']['samples'] or
                any(v is not None and (type(v) not in (float,int) or not math.isfinite(v) or v<0) for v in scan)):
            return False
        transforms=m.get('static_tf')
        # 카메라 없는 로봇은 base/link와 lidar의 고정 TF 두 개만 보냅니다.
        frames=self.config['frames']
        expected={(frames['base_footprint'],frames['base_link']),
                  (frames['base_link'],frames['scan'])}
        if self.config['camera']['enabled']:
            expected.add((frames['base_link'],frames['camera_optical']))
        if self.config.get('tag_camera',{}).get('enabled'):
            expected.add((frames['base_link'],frames['tag_camera_optical']))
        # 장착 레이어가 선택된 예찰만 런타임에서 발행하는 센서 TF 네 개를 추가합니다.
        if self.config.get('scout_mount_asset'):
            prefix=frames['base_link'].rsplit('/',1)[0]+'/' if '/' in frames['base_link'] else ''
            expected.update((frames['base_link'],prefix+name) for name in
                            ('bmany_camera_link','camera_color_optical_frame','picam_frame','picam_optical_frame'))
        if not isinstance(transforms,list) or len(transforms)!=len(expected):return False
        for t in transforms:
            if not isinstance(t,dict) or not isinstance(t.get('parent'),str) or not isinstance(t.get('child'),str):return False
            if not finite_vector(t.get('translation'),3) or not finite_vector(t.get('rotation_xyzw'),4):return False
        if {(t['parent'],t['child']) for t in transforms} != expected:return False
        return True

    def poll(self):
        for m in self.transport.receive():
            if not self.valid(m):continue
            if m['session']!=self.session:
                if self.session is not None and time.monotonic()-self.last_seen<self.config['runtime']['transport_timeout_s']:
                    continue
                self.session=m['session'];self.last_packet=-1;self.last_stamp=-1;self.static_sent=False
                self.pending_states.clear()
                self.get_logger().info('Isaac Sim 연결됨. odom 원점은 시작 위치입니다; map 위치추정은 별도입니다.')
            if m['seq']<=self.last_packet or m['stamp_ns']<=self.last_stamp:continue
            self.last_packet,self.last_stamp=m['seq'],m['stamp_ns'];self.last_seen=time.monotonic()
            self.link_lost=False
            if self.arm_server is not None:self.arm_server.observe(m['session'],m.get('arm'))
            if self.state_clock_delay_ns:self.pending_states.append(m)
            else:self.publish_state(m)
        if self.state_clock_delay_ns:self.publish_ready_states()
        if self.session is not None and time.monotonic()-self.last_seen>self.config['runtime']['transport_timeout_s'] and not self.link_lost:
            self.get_logger().warning('시뮬레이션 데이터가 멈췄습니다. 새 속도 명령 전달을 중단합니다.')
            self.link_lost=True
        if self.camera_ros is not None and not self.link_lost:
            active=True
            if self.config['camera'].get('on_demand',False):
                active=self.camera_ros.image_pub.get_subscription_count()>0
                now=time.monotonic()
                if self.session is not None and now-self.last_camera_activity>=.2:
                    self.transport.send(dict(kind='camera_activity',session=self.session,
                        seq=time.monotonic_ns(),sent=now,active=active))
                    self.last_camera_activity=now
            if active:
                if self.state_clock_delay_ns:
                    self.camera_ros.publish(self.session,self.get_clock().now().nanoseconds-self.state_clock_delay_ns)
                else:self.camera_ros.publish(self.session)
        if self.tag_camera_ros is not None and not self.link_lost:
            self.tag_camera_ros.publish(self.session)

    def publish_ready_states(self) -> None:
        """시계 정지 때 큐는 유한 크기이며 만료 패킷은 뒤늦게 재생하지 않는다."""
        now=time.monotonic();clock_ns=self.get_clock().now().nanoseconds
        timeout=self.config['runtime']['transport_timeout_s']
        while self.pending_states:
            m=self.pending_states[0]
            if now-m['sent']>timeout or clock_ns-m['stamp_ns']>500_000_000:
                self.pending_states.popleft();continue
            if clock_ns<m['stamp_ns']+self.state_clock_delay_ns:break
            self.publish_state(self.pending_states.popleft())

    def publish_state(self,m):
        if self.mechanical_server is not None:
            self.mechanical_server.observe(m['session'],m.get('basket_alignment'))
        ns=m['stamp_ns'];frames=self.config['frames']
        if self.clock_pub is not None:
            clock=ClockMessage();stamp_message(clock.clock,ns);self.clock_pub.publish(clock)
        x,y,yaw,v,w=m['odom']
        odom=Odometry();stamp_message(odom.header.stamp,ns)
        odom.header.frame_id=frames['odom'];odom.child_frame_id=frames['base_footprint']
        odom.pose.pose.position.x=x;odom.pose.pose.position.y=y
        odom.pose.pose.orientation.z=math.sin(yaw/2);odom.pose.pose.orientation.w=math.cos(yaw/2)
        odom.twist.twist.linear.x=v;odom.twist.twist.angular.z=w
        # 초기 보수적 가정. 실제 센서/주행 시험으로 조정할 값입니다.
        for i,value in enumerate([.0025,.0025,1e6,1e6,1e6,.01]):odom.pose.covariance[i*7]=value
        for i,value in enumerate([.01,1e6,1e6,1e6,1e6,.04]):odom.twist.covariance[i*7]=value
        self.odom_pub.publish(odom)
        tf=TransformStamped();tf.header=odom.header;tf.child_frame_id=odom.child_frame_id
        tf.transform.translation.x=x;tf.transform.translation.y=y
        tf.transform.rotation=odom.pose.pose.orientation;self.tf.sendTransform(tf)
        if not self.static_sent:
            transforms=[]
            for entry in m['static_tf']:
                t=TransformStamped();stamp_message(t.header.stamp,ns)
                t.header.frame_id=entry['parent'];t.child_frame_id=entry['child']
                t.transform.translation.x,t.transform.translation.y,t.transform.translation.z=entry['translation']
                t.transform.rotation.x,t.transform.rotation.y,t.transform.rotation.z,t.transform.rotation.w=entry['rotation_xyzw']
                transforms.append(t)
            self.static_tf.sendTransform(transforms);self.static_sent=True
        joints=JointState();stamp_message(joints.header.stamp,ns)
        joints.header.frame_id=frames['base_link'];joints.name=self.config['base']['wheel_joints']
        joints.position=m['joint_positions'];joints.velocity=m['joint_velocities'];self.joint_pub.publish(joints)
        if m['scan'] is not None:
            cfg=self.config['lidar'];scan=LaserScan();stamp_message(scan.header.stamp,ns)
            scan.header.frame_id=frames['scan'];scan.angle_min=-math.pi
            scan.angle_increment=2*math.pi/cfg['samples'];scan.angle_max=scan.angle_min+(cfg['samples']-1)*scan.angle_increment
            scan.time_increment=0.0;scan.scan_time=1.0/cfg['fps']
            scan.range_min=float(cfg['range_min_m']);scan.range_max=float(cfg['range_max_m'])
            scan.ranges=[math.inf if v is None else float(v) for v in m['scan']]
            self.scan_pub.publish(scan)

    def close(self):
        if self.session is not None:self.command(Twist())
        if self.arm_server is not None:self.arm_server.close()
        if self.mechanical_server is not None:self.mechanical_server.close()
        self.transport.close()
        self.destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node=None;executor=None
    try:
        node=SimRosAdapter()
        # 팔 execute는 wall 시간 조건변수로 대기합니다. 센서 poll/cancel 처리는 병행합니다.
        executor=MultiThreadedExecutor(num_threads=4)
        executor.add_node(node);executor.spin()
    except (KeyboardInterrupt,ExternalShutdownException):pass
    finally:
        if node is not None and node.arm_server is not None:node.arm_server.request_stop()
        if executor is not None:executor.shutdown()
        if node is not None:node.close()
        if rclpy.ok():rclpy.shutdown()
