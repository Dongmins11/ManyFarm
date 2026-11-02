"""명령 만료·센서 만료 시 0 명령 발행 검증. 로봇/ROS 그래프 접속 없음."""
import threading
import time
import unittest
from types import SimpleNamespace as NS
from farm_common.station_wall_runtime import StationWallRuntime

class OutputTests(unittest.TestCase):
    def runtime(self):
        obj=StationWallRuntime.__new__(StationWallRuntime);obj.lock=threading.Lock()
        obj.active=True;obj.command=(-.05,.03);obj.command_at=time.monotonic()
        obj.scan=obj.odom=object();obj.scan_at=obj.odom_at=time.monotonic()
        obj.c={'command_timeout_s':.25};obj._fresh=lambda *a:True
        self.sent=[];obj.pub=NS(publish=self.sent.append)
        return obj
    def test_expired_command_stops(self):
        obj=self.runtime();obj.command_at-=1;obj._publish()
        self.assertEqual(self.sent[-1].linear.x,0)
        self.assertEqual(self.sent[-1].angular.z,0)
    def test_expired_sensor_stops(self):
        obj=self.runtime();obj._fresh=lambda *a:False;obj._publish()
        self.assertEqual(self.sent[-1].linear.x,0)
    def test_inactive_does_not_compete_with_nav2(self):
        obj=self.runtime();obj.active=False;obj._publish();self.assertEqual(self.sent,[])
    def test_stop_is_zero_and_disables_output(self):
        obj=self.runtime();obj.stop();obj._publish()
        self.assertEqual(len(self.sent),1);self.assertEqual(self.sent[0].linear.x,0)
        self.assertFalse(obj.active)

if __name__=='__main__':unittest.main()
