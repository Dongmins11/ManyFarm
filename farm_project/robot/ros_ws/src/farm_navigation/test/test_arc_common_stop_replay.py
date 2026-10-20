"""기존 공통 MotionMonitor의 실제 코드를 가짜 ROS·시계로 호출한다."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

class StopReplayTest(unittest.TestCase):
    def run_monitor(self,kind):
        path=Path(__file__).parents[1]/'farm_navigation/motion_monitor.py'
        mods={}
        for name in ['nav_msgs','nav_msgs.msg','rclpy','rclpy.node','rclpy.callback_groups']:
            mods[name]=types.ModuleType(name)
        mods['nav_msgs.msg'].Odometry=object;mods['rclpy.node'].Node=object;mods['rclpy.callback_groups'].CallbackGroup=object
        # 상대 import는 실제 공통 NavigationSettings를 사용한다.
        with patch.dict(sys.modules,mods):
            spec=importlib.util.spec_from_file_location('farm_navigation._stop_replay',path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        from farm_navigation.navigation_types import NavigationSettings
        settings=NavigationSettings(stopped_linear_mps=.005,stopped_angular_rps=.02,settle_s=.8,settle_timeout_s=5.)
        m=module.MotionMonitor.__new__(module.MotionMonitor)
        m._settings=settings;m._lock=threading.Lock();m._message=None;m._received=0.
        data=json.loads((Path(__file__).parent/'data/arc_odom_failure_20261020.json').read_text())
        start=1792462841847494151
        rows=[r for r in data if r[0]>=start]
        now=[0.];index=[0]
        def feed():
            while index[0]<len(rows) and (rows[index[0]][0]-start)/1e9<=now[0]:
                t,v,y,w=rows[index[0]];index[0]+=1
                if kind=='moving':v=.02
                if kind=='frozen':t=rows[0][0]
                if kind=='stale' and index[0]>2:continue
                if kind=='reverse_time' and index[0]>5:t=rows[0][0]-1
                stamp=types.SimpleNamespace(sec=t//10**9,nanosec=t%10**9)
                twist=types.SimpleNamespace(linear=types.SimpleNamespace(x=v,y=y),angular=types.SimpleNamespace(z=w))
                m._on_odom(types.SimpleNamespace(header=types.SimpleNamespace(stamp=stamp),twist=types.SimpleNamespace(twist=twist)))
        def sleep(t):now[0]+=t;feed()
        with patch.object(module.time,'monotonic',lambda:now[0]),patch.object(module.time,'sleep',sleep):
            feed();stamp=m.wait_stopped(lambda:None)
        return now[0],stamp
    def test_record_stops(self):
        duration,stamp=self.run_monitor('record')
        self.assertLess(duration,5.);self.assertGreaterEqual(duration,.8)
    def test_moving_rejected(self):
        with self.assertRaises(RuntimeError):self.run_monitor('moving')
    def test_frozen_time_rejected(self):
        with self.assertRaises(RuntimeError):self.run_monitor('frozen')
    def test_stale_rejected(self):
        with self.assertRaises(RuntimeError):self.run_monitor('stale')
    def test_reversed_time_rejected(self):
        with self.assertRaises(RuntimeError):self.run_monitor('reverse_time')

if __name__=='__main__':unittest.main()
