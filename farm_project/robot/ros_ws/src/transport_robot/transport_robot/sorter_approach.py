"""Configured route observation and stopped handoff to the unchanged distance trial."""
from farm_navigation.operation_clock import operation_time
import json
import math
import threading
import time
from dataclasses import replace

class MarkerHandoff(Exception):
    pass

def in_corridor(x,y,a,b,width):
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=math.hypot(dx,dy)
    along=((x-a[0])*dx+(y-a[1])*dy)/length
    cross=abs((x-a[0])*dy-(y-a[1])*dx)/length
    return -.05<=along<=length+.05 and cross<=width

class SorterApproach:
    def __init__(self,node):
        from std_msgs.msg import String
        from std_srvs.srv import SetBool
        self.node=node;self.c=node.profile['sorter_distance_handoff']
        destination=node.profile['registry']['destinations'][self.c['station_id']]
        if destination['approach_node_id']!=self.c['approach_end_node']:
            raise ValueError('Sorter handoff endpoint differs from destination')
        profile=node.profile['precision_registry']['profiles'][self.c['docking_profile']]
        if not profile.get('configured') or 'DOCK' not in profile.get('allowed_operations',[]) or not profile.get('distance_heading_trial'):
            raise ValueError('Sorter distance docking profile unavailable')
        if profile['target_marker_id']!=self.c['marker_id']:raise ValueError('Sorter marker ID mismatch')
        self.lock=threading.Lock();self.armed=False;self.samples=[];self.last_stamp=0
        self.a=node.graph.nodes[self.c['observation_start_node']]
        self.b=node.graph.nodes[self.c['approach_end_node']]
        if math.dist(self.a,self.b)<.05:raise ValueError('Sorter observation edge too short')
        if not any(e.start==self.c['observation_start_node'] and e.end==self.c['approach_end_node'] for e in node.graph.edges):
            raise ValueError('Sorter approach requires directed graph edge')
        self.yaw=math.atan2(self.b[1]-self.a[1],self.b[0]-self.a[0])
        self.SetBool=SetBool
        self.service=node.create_client(SetBool,'precision/observe_sorter',callback_group=node.callbacks)
        self.sub=node.create_subscription(String,'precision/marker_observations',self.observe,1,callback_group=node.callbacks)

    def applies(self,r):
        return r.kind=='unload' and r.station_id==self.c['station_id']

    def enable(self,value):
        if not self.service.wait_for_service(timeout_sec=5):raise RuntimeError('Sorter observation service unavailable')
        q=self.SetBool.Request();q.data=value;future=self.service.call_async(q)
        deadline=operation_time(self.node)+15
        while not future.done():
            if operation_time(self.node)>deadline:raise TimeoutError('Sorter observation service timeout')
            time.sleep(.02)
        result=future.result()
        if not result.success:raise RuntimeError('Sorter observation: '+result.message)

    def observe(self,msg):
        with self.lock:
            if not self.armed:return
            try:
                r=json.loads(msg.data);stamp=r['stamp_ns']
                if stamp<=self.last_stamp:return
                self.last_stamp=stamp
                age=(self.node.get_clock().now().nanoseconds-stamp)/1e9
                marker=next((m for m in r['markers'] if m['marker_id']==self.c['marker_id']),None)
                if r.get('frame_id')!=self.node.settings.base_frame or not 0<=age<=self.c['max_age_s'] or marker is None:
                    self.samples=[];return
                x,y,z=marker['marker_position_in_base_m']
                if not all(math.isfinite(v) for v in (x,y,z)) or not self.c['min_marker_forward_m']<=x<=self.c['max_marker_forward_m'] or abs(math.atan2(y,x))>self.c['max_bearing_rad']:
                    self.samples=[];return
                if self.samples and (stamp-self.samples[-1])/1e9>self.c['max_age_s']:self.samples=[]
                self.samples=(self.samples+[stamp])[-self.c['samples']:]
            except (KeyError,ValueError,TypeError):self.samples=[]

    def check_handoff(self):
        with self.lock:
            if not self.armed or len(self.samples)<self.c['samples']:return
            if not 0<=(self.node.get_clock().now().nanoseconds-self.samples[-1])/1e9<=self.c['max_age_s']:return
        p=self.node._pose
        if p is None:return
        yaw=math.atan2(p[1,0],p[0,0])
        error=math.atan2(math.sin(yaw-self.yaw),math.cos(yaw-self.yaw))
        if in_corridor(p[0,3],p[1,3],self.a,self.b,self.c['corridor_half_width_m']) and abs(error)<=self.c['max_heading_error_rad']:
            raise MarkerHandoff('Stable marker on configured sorter approach edge')

    def move(self,request):
        node=self.node;nav=node.navigator
        current=node.poses.current(node.check_motion)
        # Start inside the approach corridor without routing backwards to its entry.
        if not in_corridor(current[0,3],current[1,3],self.a,self.b,self.c['corridor_half_width_m']):
            nav.navigate(self.a,self.yaw)
        node.check_motion()
        self.enable(True)
        try:
            with self.lock:self.samples=[];self.last_stamp=0;self.armed=True
            try:
                result=nav.navigate(self.b,self.yaw)
            except MarkerHandoff:
                # navigate has returned and released the nav lease; now terminate
                # its own goal and verify measured stop before precision starts.
                with self.lock:self.armed=False
                nav.cancel_nav()
                node.controller.check()
                node.get_logger().info('Sorter handoff: Nav2 terminated, measured stop confirmed; distance docking next')
                result=None
            finally:
                with self.lock:self.armed=False
            return result
        finally:
            with self.lock:self.armed=False
            self.enable(False)

    def dock(self,request):
        # Keep mission/departure identity; override only this DOCK invocation.
        r=replace(request,profile_id=self.c['docking_profile'],target_marker_id=self.c['marker_id'],docking_marker_id=self.c['marker_id'])
        return self.node.docking.dock(r)
