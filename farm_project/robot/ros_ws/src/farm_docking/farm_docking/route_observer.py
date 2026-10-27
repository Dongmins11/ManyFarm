"""Observation-only helper for the removable sorter trial client."""
import json,math,time
from pathlib import Path
import numpy as np
import yaml
from .marker_geometry import transform_matrix

class RouteObserver:
    def __init__(self,node,root,profile):
        from std_msgs.msg import String
        from nav_msgs.msg import Odometry
        from std_srvs.srv import SetBool
        from rclpy.qos import qos_profile_sensor_data
        from tf2_ros import Buffer,TransformListener
        from rclpy.time import Time
        self.Time=Time;self.node=node;self.c=profile['route_observation'];self.samples=[];self.last_stamp=0
        self.last_odom=0.;self.stopped_since=None
        self.reason='no observation received';self.log_at=0.
        self.base=profile.get('base_frame','base_footprint')
        file=Path(profile.get('pose_control_file') or (root/'robot/config/docking/waffle_marker_targets.yaml'))
        if not file.is_absolute():file=root/'robot/config/docking'/file
        target=yaml.safe_load(file.read_text())['targets'][profile['pose_target']]
        self.target=np.asarray(target['T_marker_base']);self.marker_id=target['marker_id']
        self.tf=Buffer();self.listener=TransformListener(self.tf,node)
        self.sub=node.create_subscription(String,'/transport_01/precision/marker_observations',self.observe,1)
        self.odom=node.create_subscription(Odometry,'/transport_01/odom',self.on_odom,qos_profile_sensor_data)
        self.service=node.create_client(SetBool,'/transport_01/precision/observe_sorter');self.SetBool=SetBool
    def enable(self,value):
        import rclpy
        if not self.service.wait_for_service(timeout_sec=5):raise RuntimeError('Observation service unavailable; restart bringup')
        q=self.SetBool.Request();q.data=value;f=self.service.call_async(q)
        rclpy.spin_until_future_complete(self.node,f,timeout_sec=15)
        if not f.done() or not f.result().success:raise RuntimeError('Observation service failed: '+(f.result().message if f.done() else 'timeout'))
    def on_odom(self,m):
        age=(self.node.get_clock().now().nanoseconds-m.header.stamp.sec*10**9-m.header.stamp.nanosec)/1e9
        now=time.monotonic();v=m.twist.twist
        good=0<=age<=.5 and abs(v.linear.x)<.005 and abs(v.angular.z)<.02
        if not good or now-self.last_odom>.5:self.stopped_since=None
        if good and self.stopped_since is None:self.stopped_since=now
        self.last_odom=now if 0<=age<=.5 else 0.
    def stopped(self):
        return self.stopped_since is not None and time.monotonic()-self.stopped_since>=.8 and time.monotonic()-self.last_odom<.5
    def observe(self,msg):
        try:
            report=json.loads(msg.data);stamp=report['stamp_ns'];now=self.node.get_clock().now().nanoseconds
            if report.get('frame_id')!=self.base:self.reject('frame mismatch: '+str(report.get('frame_id')));return
            if stamp<=self.last_stamp:return
            self.last_stamp=stamp
            if not 0<=(now-stamp)/1e9<=self.c['max_observation_age_s']:self.reject(f'observation age {(now-stamp)/1e9:.3f}s');return
            marker=next((m for m in report['markers'] if m['marker_id']==self.marker_id),None)
            if marker is None:self.reject('marker not visible');return
            relative=np.eye(4);relative[:3,:3]=marker['marker_rotation_in_base'];relative[:3,3]=marker['marker_position_in_base_m']
            relative=relative@self.target
            if np.linalg.norm(relative[:2,3])>self.c['max_target_distance_m'] or relative[0,3]<-.005:self.reject(f'target range/behind: x={relative[0,3]:.3f} y={relative[1,3]:.3f}');return
            t=self.tf.lookup_transform('odom',self.base,self.Time(nanoseconds=stamp));v,q=t.transform.translation,t.transform.rotation
            goal=transform_matrix((v.x,v.y,v.z),(q.x,q.y,q.z,q.w))@relative
            self.reason='checking target stability';self.samples.append((stamp,goal));self.samples=self.samples[-self.c['acquire_samples']:]
        except Exception as exc:self.reject('TF/observation: '+str(exc))
    def reject(self,reason):
        self.samples=[];self.reason=reason
    def status(self):
        if time.monotonic()-self.log_at>=1.:
            self.log_at=time.monotonic()
            self.node.get_logger().info(f'Route marker: samples={len(self.samples)}/{self.c["acquire_samples"]} ready={self.ready()} reason={self.reason}')
    def ready(self):
        if len(self.samples)<self.c['acquire_samples']:return False
        now=self.node.get_clock().now().nanoseconds
        if (now-self.samples[-1][0])/1e9>self.c['max_observation_age_s'] or (self.samples[-1][0]-self.samples[0][0])/1e9>2:return False
        xy=np.array([g[:2,3] for _,g in self.samples]);a=[math.atan2(g[1,0],g[0,0]) for _,g in self.samples]
        return bool(np.max(np.linalg.norm(xy-np.median(xy,axis=0),axis=1))<=self.c['position_spread_m'] and max(abs(math.atan2(math.sin(v-a[-1]),math.cos(v-a[-1]))) for v in a)<=self.c['yaw_spread_rad'])
