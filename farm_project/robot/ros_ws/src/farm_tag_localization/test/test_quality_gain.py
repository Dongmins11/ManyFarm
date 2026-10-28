"""AMCL 해 선택을 바꾸지 않고 실제 적용된 복수 관측 근처 단일 보정 영향만 줄인다."""
from pathlib import Path
import math,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from farm_tag_localization.tag_adapter import quality_gain,correction,approach_allowed
from farm_tag_localization.runtime import Lease
class QualityGain(unittest.TestCase):
    def setUp(self) -> None:
        self.ref=dict(token='task',scan_stamp_ns=1_000_000_000,odom_anchor=[0.,0.,0.])
    def test_recent_applied_multi_reduces_single_gain(self) -> None:
        self.assertEqual(quality_gain({},self.ref,'task',2_000_000_000,[.1,0.,0.]),.1)
        self.assertAlmostEqual(correction([0,0,0],[.1,0,.1],gain=.1)[0][0],.01)
    def test_multi_or_no_reference_uses_existing_gain(self) -> None:
        for candidate,reference in [({'observation_kind':'multi_tag'},self.ref),({},None)]:
            self.assertEqual(quality_gain(candidate,reference,'task',2_000_000_000,[0,0,0]),.5)
    def test_old_wrong_token_distance_rotation_or_backwards_time_do_not_hold(self) -> None:
        for token,stamp,odom in [('other',2_000_000_000,[0,0,0]),('task',5_000_000_000,[0,0,0]),
            ('task',0,[0,0,0]),('task',2_000_000_000,[.31,0,0]),('task',2_000_000_000,[0,0,.4])]:
            self.assertEqual(quality_gain({},self.ref,token,stamp,odom),.5)
    def test_approach_gate_rejects_other_corridor_or_heading(self) -> None:
        self.assertTrue(approach_allowed([0,0,0],[.4,0,.2]))
        self.assertFalse(approach_allowed([0,0,0],[.6,0,0]))
        self.assertFalse(approach_allowed([0,0,0],[0,0,.6]))
        self.assertTrue(approach_allowed(None,[100,100,3]))
        self.assertFalse(approach_allowed([0,0,0],[.05,0,0]))
        self.assertTrue(approach_allowed([0,0,math.pi],[.2,0,-math.pi]))
    def test_lease_gate_is_finite_and_immutable_within_token(self) -> None:
        lease=Lease('s','m')
        data=dict(robot_id='s',map_id='m',token='t',sequence=1,stamp_ns=100,begin_ns=100,
            enabled=True,section_id='SEC01',approach_pose=[0,0,0])
        lease.update(data,100,0.)
        self.assertEqual(lease.approach_pose,[0,0,0])
        lease.update(dict(data,sequence=2,approach_pose=[1,0,0]),100,.1)
        self.assertEqual(lease.approach_pose,[0,0,0])
        lease.update(dict(data,token='other',sequence=3,approach_pose=[float('nan'),0,0]),100,3.)
        self.assertEqual(lease.token,'t')
