"""실제 state 발행 대기 메서드의 측정시각 보존·만료·시계 정지 회귀."""
import ast
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
SOURCE=Path(__file__).resolve().parents[1]/'ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py'
module=ast.parse(SOURCE.read_text())
cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='SimRosAdapter')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('publish_ready_states','poll')]
clock=SimpleNamespace(monotonic=lambda:10.)
namespace={'time':clock}
exec(compile(ast.Module(body=methods,type_ignores=[]),str(SOURCE),'exec'),namespace)

class ClockOrderTests(unittest.TestCase):
    def setUp(self):
        self.config={'runtime':{'transport_timeout_s':2.}}
        self.pending_states=deque(maxlen=64);self.state_clock_delay_ns=50_000_000
        self.ros_ns=1_000_000_000
        self.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=self.ros_ns))
        self.publish_state=Mock()
    def packet(self,stamp=1_000_000_000,sent=10.):return {'stamp_ns':stamp,'sent':sent}
    def flush(self):namespace['publish_ready_states'](self)
    def test_wait_for_clock_preserves_original_measurement_stamp(self):
        packet=self.packet();self.pending_states.append(packet);self.flush()
        self.publish_state.assert_not_called()
        self.ros_ns+=50_000_000;self.flush()
        self.publish_state.assert_called_once_with(packet)
        self.assertEqual(packet['stamp_ns'],1_000_000_000)
    def test_wall_expired_future_packet_dropped_during_clock_stall(self):
        self.pending_states.append(self.packet(2_000_000_000,7.));self.flush()
        self.assertFalse(self.pending_states);self.publish_state.assert_not_called()
    def test_clock_jump_does_not_replay_stale_measurements(self):
        self.pending_states.append(self.packet());self.ros_ns+=600_000_000;self.flush()
        self.assertFalse(self.pending_states);self.publish_state.assert_not_called()
    def test_clock_stall_queue_is_bounded_and_ordered(self):
        for i in range(100):self.pending_states.append(self.packet(1_000_000_000+i))
        self.flush();self.assertEqual(len(self.pending_states),64)
        self.ros_ns+=50_000_100;self.flush()
        stamps=[c.args[0]['stamp_ns'] for c in self.publish_state.call_args_list]
        self.assertEqual(stamps,list(range(1_000_000_036,1_000_000_100)))
    def test_session_change_clears_old_pending_states(self):
        self.pending_states.append(self.packet(99_000_000_000))
        self.session='old';self.last_seen=0.;self.last_packet=100;self.last_stamp=99_000_000_000
        self.static_sent=True;self.link_lost=False;self.arm_server=None
        self.camera_ros=None;self.tag_camera_ros=None
        packet=dict(self.packet(),session='new',seq=1)
        self.transport=SimpleNamespace(receive=lambda:[packet]);self.valid=lambda m:True
        self.get_logger=lambda:Mock();self.publish_ready_states=self.flush
        namespace['poll'](self)
        self.assertEqual(list(self.pending_states),[packet]);self.assertFalse(self.static_sent)

if __name__=='__main__':unittest.main()
