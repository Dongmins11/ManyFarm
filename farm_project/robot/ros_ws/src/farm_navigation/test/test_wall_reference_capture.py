"""배포 수집기 main을 fake ROS로 실행. 실제 DDS/TF 수신 시험과 구분한다."""
import contextlib
from dataclasses import dataclass, replace
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np

SCRIPT=Path(__file__).resolve().parents[4]/'tools/transfer/wall_reference_capture.py'

@dataclass
class Settings:
    base_frame:str='base_footprint'
    map_frame:str='map'
    odom_topic:str='odom'
    tf_timeout_s:float=3.

class Scenario:
    def __init__(self,mode):
        self.mode=mode;self.t=0.;self.count=0;self.callbacks={};self.calls=[]
    def tick(self):
        self.t+=.005
        return self.t
    def stamp(self,old=False):
        return types.SimpleNamespace(sec=99 if old else 100,nanosec=self.count*1000000)
    def header(self,frame,old=False):
        return types.SimpleNamespace(stamp=self.stamp(old),frame_id=frame)
    def odom(self):
        v=types.SimpleNamespace(x=0.,y=0.,z=0.)
        return types.SimpleNamespace(header=self.header('odom',self.mode=='stale_odom'),twist=types.SimpleNamespace(twist=types.SimpleNamespace(linear=v,angular=v)))
    def scan(self):
        if self.mode!='duplicate':self.count+=1
        self.callbacks['odom'](self.odom())
        if self.mode not in ('missing','no_footprint'):
            points=[types.SimpleNamespace(x=x,y=y,z=0.) for x,y in [(-.3,-.25),(.3,-.25),(.3,.25),(-.3,.25)]]
            if self.mode=='bad_footprint': points=[]
            self.callbacks['footprint'](types.SimpleNamespace(header=self.header('odom',self.mode=='stale_footprint'),polygon=types.SimpleNamespace(points=points)))
        return types.SimpleNamespace(header=self.header('laser',self.mode=='stale_scan'),angle_min=-.5,angle_max=.5,angle_increment=.01,time_increment=0.,scan_time=.1,range_min=.05,range_max=10.,ranges=[.5]*100)

class CaptureTest(unittest.TestCase):
    def run_case(self,mode):
        state=Scenario(mode)
        class Node:
            def __init__(self,*a,**k):pass
            def create_subscription(self,typ,name,cb,*a,**k):
                state.callbacks[name]=cb
                if name=='odom':cb(state.odom())
                return object()
            def get_clock(self):return types.SimpleNamespace(now=lambda:types.SimpleNamespace(nanoseconds=100000000000+state.count*1000000))
            def destroy_node(self):pass
        class Executor:
            def __init__(self,*a,**k):pass
            def add_node(self,*a):pass
            def spin(self):pass
            def shutdown(self,**k):pass
        class Pose:
            def __init__(self,node,settings):self.settings=settings
            def lookup(self,target,source,stamp,check):
                state.calls.append((target,self.settings.tf_timeout_s))
                if target=='map' and mode in ('missing','no_map'):raise RuntimeError('map 없음')
                if target=='base_footprint' and source=='odom' and mode=='bad_footprint_tf':raise RuntimeError('footprint TF 없음')
                if target=='base_footprint' and source=='laser' and mode=='missing_sensor_tf':raise RuntimeError('센서 TF 없음')
                return np.eye(4)
            def close(self):pass
        class Monitor:
            def __init__(self,*a):pass
            def wait_stopped(self,check):
                if mode=='initial_moving':raise RuntimeError('정지 확인 실패')
            def stationary_now(self):return not(mode=='moving' and state.count>=3)
            def close(self):pass
        class ScanQueue:
            def __init__(self,*a,**k):pass
            def get(self,timeout):
                if mode=='no_scan':
                    import queue
                    raise queue.Empty
                if mode=='interrupt':raise KeyboardInterrupt
                return state.scan()
        modules={}
        def module(name,**values):
            m=types.ModuleType(name);m.__dict__.update(values);modules[name]=m;return m
        module('rclpy',init=lambda **k:setattr(state,'init_args',k['args']),ok=lambda:True,shutdown=lambda:None)
        module('rclpy.node',Node=Node)
        module('rclpy.executors',MultiThreadedExecutor=Executor)
        module('rclpy.callback_groups',ReentrantCallbackGroup=lambda:None)
        module('rclpy.qos',qos_profile_sensor_data=object())
        for package,name in [('sensor_msgs','LaserScan'),('geometry_msgs','PolygonStamped'),('nav_msgs','Odometry')]:
            module(package);module(package+'.msg',**{name:type(name,(),{})})
        module('farm_navigation')
        module('farm_navigation.navigation_types',NavigationSettings=Settings)
        module('farm_navigation.pose_provider',PoseProvider=Pose)
        module('farm_navigation.motion_monitor',MotionMonitor=Monitor)
        spec=importlib.util.spec_from_file_location('capture_under_test',SCRIPT)
        collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'capture'
            argv=['capture','--output',str(output),'--scan-topic','scan','--odom-topic','odom','--footprint-topic','footprint','--seconds','1']
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',argv),patch.object(collector.time,'monotonic',state.tick),patch.object(collector.queue,'Queue',ScanQueue),contextlib.redirect_stdout(io.StringIO()):
                try:collector.main()
                except SystemExit as error:self.assertEqual(error.code,1)
            report=json.loads((output/'capture_result.json').read_text())
            raw=output/'scans.jsonl'
            records=[json.loads(x) for x in raw.read_text().splitlines()] if raw.exists() else []
        return report,records,state
    def test_no_map_no_footprint(self):
        report,records,state=self.run_case('missing')
        self.assertTrue(report['ok']);self.assertGreaterEqual(len(records),10)
        self.assertIn('/tf:=/harvest_01/tf',state.init_args)
        self.assertIn('/tf_static:=/harvest_01/tf_static',state.init_args)
        self.assertEqual(report['optional_missing_frames']['map'],len(records))
        self.assertEqual(report['optional_missing_frames']['footprint'],len(records))
        self.assertTrue(all(timeout<=.02 for target,timeout in state.calls if target=='map'))
        self.assertNotIn('footprint_points',records[0])
    def test_optional_cases(self):
        for mode in ['no_map','no_footprint','stale_footprint','bad_footprint','bad_footprint_tf']:
            with self.subTest(mode=mode):self.assertTrue(self.run_case(mode)[0]['ok'])
    def test_all_available(self):
        report,records,_=self.run_case('normal')
        self.assertTrue(report['ok']);self.assertIn('map_from_base',records[0]);self.assertIn('footprint_points',records[0])
    def test_required_failures(self):
        for mode in ['stale_scan','stale_odom','no_scan','missing_sensor_tf','duplicate','initial_moving','moving','interrupt']:
            with self.subTest(mode=mode):
                report,records,_=self.run_case(mode)
                self.assertFalse(report['ok']);self.assertTrue(report['errors'])
                self.assertFalse(report['motion_requested'])
    def test_partial_record_preserved(self):
        report,records,_=self.run_case('moving')
        self.assertFalse(report['ok']);self.assertGreater(len(records),0)

if __name__=='__main__':unittest.main()
