"""실행 설정 보존과 곡선 속도 전달 경계 검증. ROS 구동 시험을 대체하지 않는다."""
from copy import deepcopy
import math
import unittest
import yaml
from farm_navigation.arc_isolation import CommandGate, isolated_parameters


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.controller={'controller_plugins':['HarvestApproach'],'enable_stamped_cmd_vel':False,'controller_frequency':20.,'use_sim_time':False}
        self.costmap={'global_frame':'odom','plugins':['voxel_layer','inflation_layer'],'footprint':'[[0.30,-0.25],[0.30,0.25],[-0.30,0.25],[-0.30,-0.25]]','footprint_padding':.02,'resolution':.02,'voxel_layer.observation_sources':'scan','voxel_layer.scan.data_type':'LaserScan','voxel_layer.scan.topic':'/scan_filtered','filters':[]}
        self.prefix='/harvest_01/arc_trial_1234abcd'
    def generate(self):return isolated_parameters(self.controller,self.costmap,self.prefix,'/harvest_01/scan_filtered','/harvest_01/odom')
    def test_source_unchanged(self):
        before=deepcopy((self.controller,self.costmap));self.generate();self.assertEqual(before,(self.controller,self.costmap))
    def test_namespaces_and_ids(self):
        result=self.generate();self.assertEqual(set(result),{self.prefix+'/controller_server',self.prefix+'/local_costmap/local_costmap'})
        self.assertEqual(result[self.prefix+'/controller_server']['ros__parameters']['controller_plugins'],['TransferArc'])
    def test_costmap_geometry_preserved(self):
        cp=self.generate()[self.prefix+'/local_costmap/local_costmap']['ros__parameters']
        for key in ('footprint','footprint_padding','resolution','global_frame','plugins'):self.assertEqual(cp[key],self.costmap[key])
    def test_actual_scan_and_odom(self):
        result=self.generate();cp=result[self.prefix+'/local_costmap/local_costmap']['ros__parameters']
        self.assertEqual(cp['voxel_layer.scan.topic'],'/harvest_01/scan_filtered')
        self.assertEqual(result[self.prefix+'/controller_server']['ros__parameters']['odom_topic'],'/harvest_01/odom')
    def test_yaml_roundtrip(self):
        result=self.generate();self.assertEqual(yaml.safe_load(yaml.safe_dump(result)),result)
        self.assertNotIn('filters',result[self.prefix+'/local_costmap/local_costmap']['ros__parameters'])
    def test_unknown_sensor_rejected(self):
        self.costmap['voxel_layer.scan.data_type']='PointCloud2'
        with self.assertRaises(ValueError):self.generate()
    def test_missing_geometry_rejected(self):
        del self.costmap['footprint']
        with self.assertRaises(ValueError):self.generate()
    def test_stamped_rejected(self):
        self.controller['enable_stamped_cmd_vel']=True
        with self.assertRaises(ValueError):self.generate()
    def test_sim_time_inherited(self):
        self.controller['use_sim_time']=True
        self.assertTrue(self.generate()[self.prefix+'/controller_server']['ros__parameters']['use_sim_time'])


class GateTests(unittest.TestCase):
    def test_disarmed_never_forwards(self):self.assertFalse(CommandGate().accept(-.01,.1,1))
    def test_valid(self):
        g=CommandGate();g.arm(1);self.assertTrue(g.accept(-.01,.1,1.1));self.assertFalse(g.expired(1.2))
    def test_zero_allowed(self):
        g=CommandGate();g.arm(1);self.assertTrue(g.accept(0,0,1.1))
    def test_limits_and_nan_latch(self):
        for v,w in ((.01,.1),(-.026,.1),(-.01,.19),(-.01,-.01),(math.nan,.1),(-.01,math.inf)):
            with self.subTest(v=v,w=w):
                g=CommandGate();g.arm(1);self.assertFalse(g.accept(v,w,1.1));self.assertFalse(g.accept(-.01,.1,1.2))
                with self.assertRaises(RuntimeError):g.arm(2)
    def test_other_action_blocks(self):
        g=CommandGate();g.arm(1);self.assertFalse(g.accept(-.01,.1,1.1,True));self.assertTrue(g.error)
    def test_command_timeout(self):
        g=CommandGate();g.arm(1);g.accept(-.01,.1,1.1);self.assertTrue(g.expired(1.401));self.assertFalse(g.accept(-.01,.1,1.5))
    def test_initial_response_timeout(self):
        g=CommandGate();g.arm(1);self.assertFalse(g.expired(5.9));self.assertTrue(g.expired(6.01))
    def test_late_callback_cannot_reopen(self):
        g=CommandGate();g.arm(1);g.accept(-.01,.1,1.1)
        self.assertFalse(g.accept(-.01,.1,1.5));self.assertTrue(g.error)
    def test_close(self):
        g=CommandGate();g.arm(1);g.close();self.assertFalse(g.accept(-.01,.1,1.1));self.assertFalse(g.expired(100))

if __name__=='__main__':unittest.main()
