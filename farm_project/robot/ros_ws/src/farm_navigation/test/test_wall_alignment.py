"""벽 측정 연속성·독립 설정·명령 범위 오프라인 시험."""
import copy
import json
import math
from pathlib import Path
import unittest
import numpy as np
from farm_navigation.wall_observation import WallTracker
from farm_navigation.wall_trial_support import isolated_parameters,WallCommandGate

ROOT=Path(__file__).resolve().parents[4]
CONFIG=json.loads((ROOT/'config/robots/vicpinky/transfer/wall_alignment_trial.json').read_text())

def record(distance=.525,angle=0.,stamp=1_000_000_000):
    a=np.linspace(-.6,.6,121)
    return {'stamp_ns':stamp,'base_from_scan':np.eye(4).tolist(),'odom_from_base':np.eye(4).tolist(),
            'scan':{'ranges':(distance/np.cos(a-angle)).tolist(),'angle_min':float(a[0]),
                    'angle_increment':float(a[1]-a[0]),'range_min':.01,'range_max':10.}}

class WallTests(unittest.TestCase):
    def test_plane(self):
        t=WallTracker(CONFIG['observation'])
        for i in range(5):r=t.observe(record(angle=.04,stamp=1_000_000_000+i*100_000_000))
        self.assertTrue(r['ready']);self.assertAlmostEqual(r['distance_m'],.525,places=8)
        self.assertAlmostEqual(r['angle_rad'],.04,places=8)
    def test_translation_along_wall(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        r=record(stamp=1_100_000_000);r['odom_from_base'][1][3]=.1
        self.assertAlmostEqual(t.observe(r)['distance_m'],.525)
    def test_distance_jump(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        with self.assertRaises(ValueError):t.observe(record(.55,stamp=1_100_000_000))
    def test_angle_jump(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        with self.assertRaises(ValueError):t.observe(record(angle=.1,stamp=1_100_000_000))
    def test_duplicate(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        with self.assertRaises(ValueError):t.observe(record())
    def test_missing_wall(self):
        r=record();r['scan']['ranges']=[None]*121
        with self.assertRaises(ValueError):WallTracker(CONFIG['observation']).observe(r)
    def test_fixed_frame_translation(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        r=record(.515,stamp=1_100_000_000);r['odom_from_base'][0][3]=.01
        self.assertAlmostEqual(t.observe(r)['x'],.525)
    def test_gap(self):
        t=WallTracker(CONFIG['observation']);t.observe(record())
        with self.assertRaises(ValueError):t.observe(record(stamp=2_000_000_000))
    def test_tilt(self):
        r=record();r['odom_from_base'][2][0]=.1
        with self.assertRaises(ValueError):WallTracker(CONFIG['observation']).observe(r)
    def test_configuration_preserves_original(self):
        cm={'global_frame':'odom','footprint':'[[.3,.25],[-.3,.25],[-.3,-.25],[.3,-.25]]','plugins':['voxel_layer'],
            'resolution':.02,'footprint_padding':.02,'voxel_layer.observation_sources':'scan',
            'voxel_layer.scan.data_type':'LaserScan','voxel_layer.scan.topic':'scan_filtered'}
        original=copy.deepcopy(cm)
        conf=isolated_parameters({},cm,'/test','/robot/scan','/robot/odom',CONFIG)
        self.assertEqual(cm,original)
        result=conf['/test/local_costmap/local_costmap']['ros__parameters']
        self.assertEqual(result['footprint'],cm['footprint']);self.assertEqual(result['resolution'],.02)
        self.assertEqual(result['footprint_padding'],.02)
        self.assertEqual(result['voxel_layer.scan.topic'],'/robot/scan')
    def test_gate_forward_both_turns(self):
        g=WallCommandGate(.01,.05);g.arm(0)
        self.assertTrue(g.accept(.01,-.05,.1));self.assertTrue(g.accept(.01,.05,.2))
    def test_gate_reverse_rejected(self):
        g=WallCommandGate(.01,.05);g.arm(0)
        self.assertFalse(g.accept(-.001,0,.1));self.assertFalse(g.accept(.001,0,.2))
    def test_gate_stale(self):
        g=WallCommandGate(.01,.05);g.arm(0);g.accept(.01,0,.1)
        self.assertTrue(g.expired(.41))
    def test_gate_nan(self):
        g=WallCommandGate(.01,.05);g.arm(0);self.assertFalse(g.accept(math.nan,0,.1))

if __name__=='__main__':unittest.main()
