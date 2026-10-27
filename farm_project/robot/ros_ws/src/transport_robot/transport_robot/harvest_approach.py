"""Observe during pickup navigation; stop Nav2 before the shared precision action."""
import json,time,threading
from .sorter_approach import MarkerHandoff
class HarvestApproach:
    def __init__(self,node):
        from std_msgs.msg import String
        from std_srvs.srv import SetBool
        self.node=node;self.SetBool=SetBool;self.armed=False;self.lock=threading.Lock();self.ready=None;self.observer_id=None
        self.c=node.profile['pickup_workflow']['route_handoff']
        self.profile=node.profile['pickup_workflow']['approach_profile']
        self.service=node.create_client(SetBool,'precision/observe_harvest',callback_group=node.callbacks)
        self.sub=node.create_subscription(String,'precision/harvest_route_target',self.observe,1,callback_group=node.callbacks)
    def applies(self,r):return r.kind=='pickup'
    def enable(self,value):
        if not self.service.wait_for_service(timeout_sec=5):raise RuntimeError('Harvest observation service unavailable')
        q=self.SetBool.Request();q.data=value;f=self.service.call_async(q);deadline=time.monotonic()+15
        while not f.done():
            if time.monotonic()>deadline:raise TimeoutError('Harvest observation request timeout')
            time.sleep(.02)
        result=f.result()
        if not result.success:raise RuntimeError(result.message)
        self.observer_id=result.message if value else None
    def observe(self,msg):
        try:r=json.loads(msg.data)
        except (ValueError,TypeError):return
        with self.lock:
            self.ready=r if self.armed and r.get('observer_id')==self.observer_id else None
    def check_handoff(self):
        with self.lock:
            r=self.ready
            if not self.armed or not r or r.get('profile')!=self.profile:return
            age=(self.node.get_clock().now().nanoseconds-r['stamp_ns'])/1e9
            if not 0<=age<=self.c['max_ready_age_s']:return
            if r.get('expired'):raise RuntimeError('Harvest route observation expired; navigation must stop')
            if not r.get('ready'):return
        raise MarkerHandoff('Harvest42 recognized; stop for target acquisition')
    def move(self,request):
        self.enable(True);handoff=False
        try:
            with self.lock:self.ready=None;self.armed=True
            self.node.get_logger().info('Harvest route: marker42 observation active during navigation')
            try:return self.node.navigator.navigate(request.xy,request.yaw)
            except MarkerHandoff:
                with self.lock:self.armed=False
                self.node.navigator.cancel_nav()
                self.node.controller.check()
                handoff=True
                self.node.get_logger().info('Harvest route handoff: Nav2 canceled and stopped; fresh stationary marker42 acquisition -> precision approach')
                return None
        finally:
            with self.lock:self.armed=False;self.ready=None
            # Keep the camera on for the immediately following stationary acquisition.
            if not handoff:self.enable(False)
