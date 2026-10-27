"""운송 장치 구성/구독 카메라 lease 회귀. 실제 Isaac 시험은 tools의 smoke로 분리."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/p) for p in ('sim/ros_ws/src/farm_sim_runtime','sim/ros_ws/src/farm_sim_devices','robot/ros_ws/src/farm_common')]
from farm_sim_runtime.fleet_config import load_fleet
from farm_sim_runtime.harvest_physics import load_physics_profile
from farm_sim_devices.camera_sim import CameraSim


class HardwareConfigTests(unittest.TestCase):
    def test_standalone_and_full_fleet_without_sensor_or_port_collisions(self):
        for name,ids in [('transport_hardware_fleet',['transport_01']),
                         ('transport_fleet',['scout_01','harvest_01','transport_01']),
                         ('harvest_fleet',['scout_01','harvest_01'])]:
            configs,task=load_fleet(ROOT,Path('sim/ros_ws/src/farm_sim_config/config/'+name+'.json'))
            self.assertEqual([c['robot_id'] for c in configs],ids)
            profile=load_physics_profile(ROOT,configs)
            self.assertEqual(profile is None,len(ids)==1)
            self.assertEqual(task['harvest_robot'] is None,len(ids)==1)

    def test_arm_requires_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'sim').mkdir()
            config=ROOT/'sim/ros_ws/src/farm_sim_config/config'
            for name in ('harvest','station_spawn'):
                (root/'sim'/f'{name}.json').write_text((config/f'{name}.json').read_text())
            path=root/'sim/fleet.json'
            path.write_text(json.dumps(dict(station_config='sim/station_spawn.json',
                device_configs=['sim/harvest.json'],clock=dict(command_port=17690,telemetry_port=17691))))
            with self.assertRaisesRegex(ValueError,'evaluation_config'):load_fleet(root,path)

    def test_camera_mount_rotation_is_rigid_and_intrinsics_match_resolution(self):
        c=json.loads((ROOT/'sim/ros_ws/src/farm_sim_config/config/transport.json').read_text())['camera']
        t=np.asarray(c['T_base_optical'])
        np.testing.assert_allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-10)
        self.assertAlmostEqual(np.linalg.det(t[:3,:3]),1.)
        self.assertEqual([c['width'],c['height']],[c['camera_info']['width'],c['camera_info']['height']])


class CameraDemandTests(unittest.TestCase):
    def setUp(self):
        self.camera=CameraSim.__new__(CameraSim)
        self.camera.config=dict(on_demand=True,shm_name='test')
        self.camera.session='current';self.camera.active=True
        self.camera.activity_sequence=-1;self.camera.activity_deadline=-float('inf')
        self.camera.activity_requested=False;self.camera.last_stamp=-1.
        self.camera.camera=Mock()
        self.camera.camera.get_current_frame.return_value={'rendering_time':12.}

    def packet(self,**values):
        return dict(dict(kind='camera_activity',session='current',seq=1,sent=10.,active=True),**values)

    def test_no_subscriber_pause_then_resume_expire_disables_renderer(self):
        c=self.camera;c.update_activity(10.)
        self.assertFalse(c.active);self.assertFalse(c.publish([],1.))
        c.camera._render_product.hydra_texture.set_updates_enabled.assert_called_with(False)
        self.assertTrue(c.accept_activity(self.packet(),10.));c.update_activity(10.)
        self.assertTrue(c.active);c.camera.resume.assert_called_once()
        self.assertEqual(c.last_stamp,12.)
        c.update_activity(12.01);self.assertFalse(c.active)
        c.camera._render_product.hydra_texture.set_updates_enabled.assert_called_with(False)

    def test_stale_foreign_replayed_invalid_messages_do_not_reactivate(self):
        c=self.camera
        for change in (dict(session='old'),dict(sent=7.),dict(sent=11.),dict(sent=float('nan')),
                       dict(active=1),dict(seq=True),dict(kind='cmd')):
            self.assertFalse(c.accept_activity(self.packet(**change),10.))
        self.assertTrue(c.accept_activity(self.packet(active=False),10.))
        self.assertFalse(c.accept_activity(self.packet(),10.))
        c.update_activity(10.);self.assertFalse(c.active)

    def test_legacy_continuous_camera_preserved(self):
        c=self.camera;c.config.pop('on_demand');c.update_activity(10.)
        self.assertTrue(c.active);c.camera.pause.assert_not_called()
        self.assertFalse(c.accept_activity(self.packet(active=False),10.))


if __name__=='__main__':unittest.main()
